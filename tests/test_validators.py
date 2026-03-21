"""Tests para el módulo de validación de archivos de entrada."""

import os
import sys
import tempfile

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from validators.file_validator import (
    ColumnSpec,
    ValidationResult,
    validate_file,
    validate_libro_contable,
    validate_cartola_bancaria,
    LIBRO_CONTABLE_SPEC,
    CARTOLA_BANCARIA_SPEC,
)
from src.generate_data import generate_libro_contable, generate_cartola_bancaria


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def libro_path(tmp_dir):
    path = os.path.join(tmp_dir, "libro_contable.csv")
    generate_libro_contable(path)
    return path


@pytest.fixture
def cartola_path(tmp_dir):
    path = os.path.join(tmp_dir, "cartola_bancaria.csv")
    generate_cartola_bancaria(path)
    return path


class TestValidationResult:
    def test_initial_state(self):
        r = ValidationResult(file_path="test.csv")
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_marks_invalid(self):
        r = ValidationResult(file_path="test.csv")
        r.add_error("Something broke")
        assert r.is_valid is False
        assert len(r.errors) == 1

    def test_add_warning_stays_valid(self):
        r = ValidationResult(file_path="test.csv")
        r.add_warning("Minor issue")
        assert r.is_valid is True
        assert len(r.warnings) == 1

    def test_summary_contains_status(self):
        r = ValidationResult(file_path="test.csv")
        assert "VÁLIDO" in r.summary()
        r.add_error("Error")
        assert "INVÁLIDO" in r.summary()


class TestColumnSpec:
    def test_defaults(self):
        spec = ColumnSpec(name="test_col")
        assert spec.required is True
        assert spec.dtype == "str"
        assert spec.max_length is None


class TestFileValidation:
    def test_file_not_found(self):
        result = validate_file("/nonexistent/path.csv", [])
        assert result.is_valid is False
        assert "no encontrado" in result.errors[0]

    def test_missing_required_column(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.csv")
        pd.DataFrame({"col_a": [1, 2]}).to_csv(path, index=False)
        specs = [ColumnSpec("col_b", required=True)]
        result = validate_file(path, specs)
        assert result.is_valid is False

    def test_valid_simple_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.csv")
        pd.DataFrame({"nombre": ["Ana", "Bob"], "edad": ["25", "30"]}).to_csv(path, index=False)
        specs = [
            ColumnSpec("nombre", max_length=10),
            ColumnSpec("edad", max_length=3),
        ]
        result = validate_file(path, specs)
        assert result.is_valid is True

    def test_pattern_validation(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.csv")
        pd.DataFrame({"code": ["OP-00001", "INVALID", "OP-00003"]}).to_csv(path, index=False)
        specs = [ColumnSpec("code", pattern=r"OP-\d{5}")]
        result = validate_file(path, specs)
        assert len(result.warnings) > 0  # INVALID no cumple el patrón

    def test_allowed_values(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.csv")
        pd.DataFrame({"tipo": ["CARGO", "ABONO", "OTRO"]}).to_csv(path, index=False)
        specs = [ColumnSpec("tipo", allowed_values=["CARGO", "ABONO"])]
        result = validate_file(path, specs)
        assert result.is_valid is False  # "OTRO" no es permitido


class TestLibroContableValidation:
    def test_generated_libro_is_valid(self, libro_path):
        result = validate_libro_contable(libro_path)
        assert result.is_valid is True
        assert result.stats["filas"] == 150

    def test_libro_has_correct_columns(self, libro_path):
        result = validate_libro_contable(libro_path)
        assert result.stats["columnas"] == 8


class TestCartolaBancariaValidation:
    def test_generated_cartola_is_valid(self, cartola_path):
        result = validate_cartola_bancaria(cartola_path)
        assert result.is_valid is True
        assert result.stats["filas"] == 140

    def test_cartola_has_correct_columns(self, cartola_path):
        result = validate_cartola_bancaria(cartola_path)
        assert result.stats["columnas"] == 8


class TestCrossValidation:
    def test_both_files_share_codigo_column(self, libro_path, cartola_path):
        """Verifica que ambos archivos tienen el campo de código para el match."""
        r1 = validate_libro_contable(libro_path)
        r2 = validate_cartola_bancaria(cartola_path)
        assert r1.is_valid and r2.is_valid

    def test_codigo_overlap_exists(self, libro_path, cartola_path):
        """Verifica que hay códigos compartidos entre ambos archivos."""
        df_libro = pd.read_csv(libro_path, encoding="latin-1", delimiter=";", dtype=str)
        df_cartola = pd.read_csv(cartola_path, encoding="utf-8", delimiter=",", dtype=str)

        codigos_libro = set(df_libro["Codigo_Operacion"].unique())
        codigos_cartola = set(df_cartola["COD_REF"].unique())
        overlap = codigos_libro & codigos_cartola

        assert len(overlap) > 0, "No hay códigos compartidos entre archivos"
        assert len(overlap) == 120  # Por diseño del generador


class TestETLPipeline:
    def test_full_pipeline_runs(self, tmp_dir):
        """Test de integración: verifica que el pipeline completo ejecuta sin errores."""
        from src.generate_data import generate_libro_contable, generate_cartola_bancaria
        from src.extract import extract_all
        from src.normalize import normalize_all
        from src.match import match_records

        libro_path = os.path.join(tmp_dir, "libro.csv")
        cartola_path = os.path.join(tmp_dir, "cartola.csv")
        generate_libro_contable(libro_path)
        generate_cartola_bancaria(cartola_path)

        df_libro, df_cartola = extract_all(libro_path, cartola_path)
        assert len(df_libro) > 0
        assert len(df_cartola) > 0

        libro_norm, cartola_norm = normalize_all(df_libro, df_cartola)
        assert "codigo" in libro_norm.columns
        assert "codigo" in cartola_norm.columns
        assert libro_norm["monto"].dtype == float

        results = match_records(libro_norm, cartola_norm)
        assert "matched" in results
        assert "solo_libro" in results
        assert "solo_banco" in results
        assert len(results["matched"]) > 0
