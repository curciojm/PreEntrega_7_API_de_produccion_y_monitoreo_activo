from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def get_model(provider: str):

    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=500,
        )

    elif provider == "anthropic":
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            temperature=0.4,
            max_tokens=500,
        )

    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            temperature=0.4,
            max_tokens=500,
        )

    raise ValueError(f"Proveedor no soportado: {provider}")