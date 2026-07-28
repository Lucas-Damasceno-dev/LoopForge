import os

from langchain_community.chat_models import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def get_llm_client(provider: str, model_name: str, temperature: float = 0.1) -> BaseChatModel:
    """
    Factory function to create and return an LLM client based on the provider.
    """
    if provider == "google":
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=google_api_key)
    elif provider == "ollama":
        return ChatOllama(model=model_name, temperature=temperature)
    elif provider == "openrouter":
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set.")
        return ChatOpenAI(
            model=model_name,
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
