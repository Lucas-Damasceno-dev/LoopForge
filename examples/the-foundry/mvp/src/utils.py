"""
Este arquivo contém utilitários e constantes compartilhadas para o estado do grafo.
"""
from enum import Enum


class Agent(Enum):
    """
    Representa os agentes (nós) no nosso grafo de trabalho.
    """
    CPO = "cpo"
    PRODUCT_MANAGER = "product_manager"
    TECH_LEAD = "tech_lead"
    DEVELOPER = "developer"
    QA = "qa"
    FINISH = "FINISH" # Estado de finalização do grafo

class StateKey(Enum):
    """
    Representa as chaves usadas no dicionário de estado do grafo.
    """
    NEXT_AGENT = "next_agent"
    # Adicionar outras chaves de estado aqui no futuro
    # Ex: EPIC = "epic", USER_STORY = "user_story", etc.

    def __str__(self):
        return self.value
