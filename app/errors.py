from schemas import LLMError, LLMErrorType


def classify_error(error: Exception) -> LLMError:
    status_code = getattr(error, "status_code", None)

    # Clave inválida / no autorizado
    if status_code == 401:
        return LLMError(
            LLMErrorType.KEY,
            "Las credenciales del proveedor no son válidas.",
        )

    # Límite de solicitudes o cuota
    if status_code == 429:
        return LLMError(
            LLMErrorType.RATE_LIMIT,
            "Se alcanzó el límite de solicitudes del proveedor.",
        )

    return LLMError(
        LLMErrorType.UNKNOWN,
        "Ocurrió un error inesperado, intente más tarde.",
    )