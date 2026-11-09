"""Registro de modelos: nombre del candidato -> estimador de scikit-learn sin entrenar.

Primera entrega: solo clasificación, con 'referencia' y 'logistica'.
Importar este módulo no lee datos ni entrena nada.
"""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from comun.contratos import Candidato, Hiperparametro, Problema

# nombre de hiperparámetro -> función que convierte el valor del contrato (float | int | str)
HIPERPARAMETROS_PERMITIDOS = {
    "referencia": {},
    "logistica": {"C": float},
}
IMPLEMENTADOS = {"clasificacion": {"referencia", "logistica"}, "serie": set()}


class ErrorRegistro(ValueError):
    """El candidato pide algo que el registro no puede construir. El evaluador lo vuelve Resultado.error."""


class Referencia(ClassifierMixin, BaseEstimator):
    """Nunca actuar: la probabilidad de la clase positiva es siempre 0."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        p = np.zeros((len(X), 2))
        p[:, 0] = 1.0
        return p

    def predict(self, X):
        return np.zeros(len(X), dtype=int)


def _n_jobs_1(estimador):
    """Pone n_jobs=1 en el estimador y en todo lo anidado que lo acepte (evaluar corre en 3 hilos).

    Excepción: LogisticRegression, donde n_jobs no tiene efecto desde sklearn 1.8 (siempre usa un
    hilo con lbfgs) y ponerlo solo produce un aviso de deprecación en cada ajuste.
    """
    todos = estimador.get_params(deep=True)
    params = {}
    for nombre in todos:
        if nombre != "n_jobs" and not nombre.endswith("__n_jobs"):
            continue
        dueno = todos.get(nombre.rsplit("__", 1)[0]) if "__" in nombre else estimador
        if not isinstance(dueno, LogisticRegression):
            params[nombre] = 1
    return estimador.set_params(**params)


def _leer_hiperparametros(modelo: str, hiperparametros: list[Hiperparametro]):
    """Devuelve (valores convertidos, nombres ignorados). Un valor que no se puede convertir es error."""
    permitidos = HIPERPARAMETROS_PERMITIDOS[modelo]
    valores, ignorados = {}, []
    for h in hiperparametros:
        if h.nombre not in permitidos:
            ignorados.append(f"{h.nombre} (no permitido para {modelo})")
            continue
        if h.nombre in valores:
            ignorados.append(f"{h.nombre} (repetido, se usa el primero)")
            continue
        try:
            valor = permitidos[h.nombre](h.valor)
        except (TypeError, ValueError):
            raise ErrorRegistro(f"{modelo}: {h.nombre}={h.valor!r} no se puede convertir a número")
        if not np.isfinite(valor) or valor <= 0:
            raise ErrorRegistro(f"{modelo}: {h.nombre} debe ser un número positivo, llegó {h.valor!r}")
        valores[h.nombre] = valor
    return valores, ignorados


def construir_modelo(problema: Problema, candidato: Candidato):
    """Devuelve (estimador sin entrenar, hiperparámetros ignorados).

    - referencia: nunca actúa, sin calibrar.
    - logistica: escalado + one-hot + LogisticRegression dentro de un Pipeline,
      calibrado con CalibratedClassifierCV(cv=3).
    Lanza ErrorRegistro con un mensaje claro si el modelo no aplica o no está implementado.
    """
    modelo, tarea = candidato.modelo, problema.tipo_tarea
    if modelo not in IMPLEMENTADOS.get(tarea, set()):
        if tarea == "serie" and modelo == "logistica":
            raise ErrorRegistro("logistica no aplica a series de tiempo")
        disponibles = ", ".join(sorted(IMPLEMENTADOS.get(tarea, set()))) or "ninguno todavía"
        raise ErrorRegistro(f"modelo '{modelo}' no implementado para {tarea}; disponibles: {disponibles}")

    valores, ignorados = _leer_hiperparametros(modelo, candidato.hiperparametros)
    if modelo == "referencia":
        return Referencia(), ignorados

    semilla = problema.particion.semilla
    preparacion = ColumnTransformer([
        ("numericas", StandardScaler(), make_column_selector(dtype_include=np.number)),
        ("categoricas", OneHotEncoder(handle_unknown="ignore"),
         make_column_selector(dtype_exclude=np.number)),
    ])
    pipeline = Pipeline([
        ("preparacion", preparacion),
        ("modelo", LogisticRegression(max_iter=1000, C=valores.get("C", 1.0), random_state=semilla)),
    ])
    calibrado = CalibratedClassifierCV(estimator=pipeline, cv=3)
    return _n_jobs_1(calibrado), ignorados
