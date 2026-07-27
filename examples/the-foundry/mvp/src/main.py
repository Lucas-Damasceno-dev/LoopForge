import os
import argparse
import json # New import
from typing import TypedDict, Annotated, Literal, Optional
from dotenv import load_dotenv
from datetime import datetime # New import

import langchain # New import
from langchain_core.globals import set_llm_cache # New import
from langchain_community.cache import SQLiteCache # New import

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .utils import Agent, StateKey
from .nodes import cpo, product_manager, tech_lead, developer, qa

# --- Carregamento de Variáveis de Ambiente ---
# Carrega o .env do caminho absoluto para evitar ambiguidades
dotenv_path = "/home/ubuntu/projects/gemini/.env"
load_dotenv(dotenv_path=dotenv_path)
print(f"--- INFO: Carregando variáveis de ambiente de: {dotenv_path} ---")

# --- Configuração de Caching do LLM ---
set_llm_cache(SQLiteCache(database_path=".langchain.db"))
print("--- INFO: Caching do LLM configurado com .langchain.db ---")




# --- 1. Definição do Estado do Grafo (Padrão State) ---
class GraphState(TypedDict):
    """
    Representa o estado do nosso grafo. Funciona como o 'estado abstrato'
    no padrão de projeto State.
    """
    idea: str
    epic: dict
    user_stories: list[dict]
    tech_spec: str
    code: str
    test_report: dict
    output_dir: str
    pm_feedback: Optional[str]
    tech_lead_feedback: Optional[str]
    mock_llm: bool # New field for mock LLM flag # New field for Tech Lead feedback
    
    # A chave que o nosso router (transitionTo) usará para decidir o próximo passo
    next_agent: str
    llm_provider: str
    llm_model_name: str
    is_interactive: bool = False


# --- 2. Definição do Router (Lógica de Transição) ---
def router(state: GraphState) -> Literal["cpo", "product_manager", "tech_lead", "developer", "qa", "__end__"]:
    """
    Esta função é a nossa implementação da lógica 'transitionTo' do padrão State.
    Ela lê o estado e decide qual nó (agente) será executado em seguida.
    """
    print("---EXECUTANDO ROTEADOR---")
    
    next_agent = state.get(str(StateKey.NEXT_AGENT))
    print(f"Próximo agente: {next_agent}")

    if next_agent == Agent.PRODUCT_MANAGER.value:
        return Agent.PRODUCT_MANAGER.value
    elif next_agent == Agent.TECH_LEAD.value:
        return Agent.TECH_LEAD.value
    elif next_agent == Agent.DEVELOPER.value:
        return Agent.DEVELOPER.value
    elif next_agent == Agent.QA.value:
        return Agent.QA.value
    elif next_agent == Agent.FINISH.value:
        return END
    
    # O valor padrão caso seja o início do fluxo
    return Agent.CPO.value

# --- 3. Montagem do Grafo ---
def build_graph(checkpointer):
    """
    Constrói e compila o grafo de agentes.
    """
    # Define o grafo de estados
    workflow = StateGraph(GraphState)

    # Adiciona os nós (nossos agentes)
    workflow.add_node(Agent.CPO.value, cpo)
    workflow.add_node(Agent.PRODUCT_MANAGER.value, product_manager)
    workflow.add_node(Agent.TECH_LEAD.value, tech_lead)
    workflow.add_node(Agent.DEVELOPER.value, developer)
    workflow.add_node(Agent.QA.value, qa)

    # Define o ponto de entrada
    workflow.set_entry_point(Agent.CPO.value)

    # Adiciona as arestas condicionais (nossa lógica de transição)
    workflow.add_conditional_edges(
        Agent.CPO.value,
        router,
        {
            Agent.PRODUCT_MANAGER.value: Agent.PRODUCT_MANAGER.value,
            END: END
        }
    )
    workflow.add_conditional_edges(
        Agent.PRODUCT_MANAGER.value,
        router,
        {
            Agent.TECH_LEAD.value: Agent.TECH_LEAD.value,
            END: END
        }
    )
    workflow.add_conditional_edges(Agent.TECH_LEAD.value, router, { 
        Agent.DEVELOPER.value: Agent.DEVELOPER.value,
        Agent.PRODUCT_MANAGER.value: Agent.PRODUCT_MANAGER.value, # New: Send back to PM for iteration
        END: END
    })
    workflow.add_conditional_edges(
        Agent.DEVELOPER.value,
        router,
        {
            Agent.QA.value: Agent.QA.value,
            Agent.TECH_LEAD.value: Agent.TECH_LEAD.value, # New: Send back to Tech Lead for iteration
            END: END
        }
    )
    workflow.add_conditional_edges(Agent.QA.value, router, { END: END })

    # Compila o grafo
    app = workflow.compile(checkpointer=checkpointer)
    return app

# --- 4. Ponto de Entrada para Execução ---
if __name__ == '__main__':
    # --- Argument Parser ---
    parser = argparse.ArgumentParser(description="Executa o grafo de agentes de forma interativa ou em modo de teste.") # Re-inserted
    parser.add_argument("-i", "--idea", type=str, help="Uma ideia de aplicação para ser processada em modo de teste (não interativo).")
    parser.add_argument("--mock-llm", action="store_true", help="Se definido, os agentes irão carregar respostas pré-definidas em vez de invocar LLMs, para testes e desenvolvimento.") # New argument
    parser.add_argument("--llm-provider", type=str, default="google", help="Specify the LLM provider to use (e.g., 'google', 'ollama', 'openrouter'). Defaults to 'google'.")
    parser.add_argument("--llm-model-name", type=str, default="gemini-2.0-flash", help="Specify the LLM model name to use (e.g., 'gemini-2.0-flash', 'llama3.1', 'mistralai/mistral-7b-instruct'). Defaults to 'gemini-2.0-flash'.")
    args = parser.parse_args()

    print("Iniciando o ambiente de execução do grafo...")
    
    # Define o diretório de saída com um timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = f"./output_agent_runs/run_{timestamp}"
    os.makedirs(run_output_dir, exist_ok=True) # Create the directory
    print(f"--- INFO: Resultados das execuções serão salvos em: {run_output_dir} ---")

    with SqliteSaver.from_conn_string(":memory:") as memory:
        print("Construindo e compilando o grafo...")
        app = build_graph(checkpointer=memory)
        print("Grafo construído e compilado com sucesso.")
        
        # Define um ID de thread para a execução, permitindo que a conversa tenha memória
        config = {"configurable": {"thread_id": "user_chat_session"}}

        # Determine if running in interactive mode
        is_interactive_mode = not args.idea

        # --- Modo de Teste (Não Interativo) ---
        if args.idea:
            print(f"\n--- MODO DE TESTE ---")
            print(f"Processando a ideia: '{args.idea}'")
            try:
                # Define o input inicial para o grafo
                inputs = {"idea": args.idea, "output_dir": run_output_dir, "mock_llm": args.mock_llm, "llm_provider": args.llm_provider, "llm_model_name": args.llm_model_name, "is_interactive": is_interactive_mode}
                
                print("\n--- INVOCANDO O GRAFO ---\n")
                # Invoca o grafo com o input e configuração definidos
                final_state = app.invoke(inputs, config)
                
                print("\n--- EXECUÇÃO FINALIZADA ---")
                print("Estado final do grafo:")
                print(json.dumps(final_state, indent=2, ensure_ascii=False)) # Use json.dumps for pretty print
                print("\n--------------------------")

            except Exception as e:
                print(f"\nOcorreu um erro: {e}")

        # --- Modo Interativo ---
        else:
            print("\n--- CHAT INICIADO ---")
            print("Você está interagindo com o agente CPO.")
            print("Digite a sua ideia inicial ou 'sair' para terminar.")
            
            while True:
                try:
                    user_input = input("\nVocê (Ideia): ")
                    if user_input.lower() in ['sair', 'exit', 'quit']:
                        print("Encerrando o chat...")
                        break
                    
                    # Define o input inicial para o grafo
                    inputs = {"idea": user_input, "output_dir": run_output_dir, "mock_llm": args.mock_llm, "llm_provider": args.llm_provider, "llm_model_name": args.llm_model_name, "is_interactive": is_interactive_mode}
                    
                    print("\n--- INVOCANDO O GRAFO ---\n")
                    # Invoca o grafo com o input e configuração definidos
                    final_state = app.invoke(inputs, config)
                    
                    print("\n--- EXECUÇÃO FINALIZADA ---")
                    print("Estado final do grafo:")
                    print(json.dumps(final_state, indent=2, ensure_ascii=False)) # Use json.dumps for pretty print
                    print("\n--------------------------")
                    print("Aguardando próxima ideia...")

                except KeyboardInterrupt:
                    print("\nEncerrando o chat...")
                    break
                except Exception as e:
                    print(f"\nOcorreu um erro: {e}")
                    print("Reiniciando o ciclo de chat.")