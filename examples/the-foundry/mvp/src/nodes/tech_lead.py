#-*- coding: utf-8 -*-
"""
Nó do Tech Lead.
"""
import os
import json
from datetime import datetime, timezone
from typing import List, Optional

from ..utils import Agent, StateKey
from ..llm_factory import get_llm_client # Import the factory

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# Define Pydantic model for Tech Lead's validation feedback
class TechLeadValidationResult(BaseModel):
    needs_feedback: bool = Field(..., description="True if feedback is needed for the Product Manager, False if user stories are ready for technical specification.")
    feedback_message: str = Field(..., description="Detailed feedback message for the Product Manager if feedback is needed. If not, state that stories are clear and ready.")

# Mock data for Tech Lead's validation result
MOCK_TL_VALIDATION_RESULT_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'tl_validation_result.json')
with open(MOCK_TL_VALIDATION_RESULT_PATH, 'r', encoding='utf-8') as f:
    MOCK_TL_VALIDATION_RESULT = json.load(f)

# Mock data for Tech Lead's technical specification
MOCK_TL_TECH_SPEC_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'tl_tech_spec_data.md')
with open(MOCK_TL_TECH_SPEC_DATA_PATH, 'r', encoding='utf-8') as f:
    MOCK_TL_TECH_SPEC_DATA = f.read()

# Tech Spec Template
TECH_SPEC_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'templates', 'tech_spec_template.md')
with open(TECH_SPEC_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
    TECH_SPEC_TEMPLATE_CONTENT = f.read()


def tech_lead(state):
    """
    Recebe o estado, analisa as user stories e gera a especificação técnica ou feedback para o PM.
    """
    print("---EXECUTANDO NÓ: Tech Lead---")
    
    # Get current time for consistent date handling
    now_iso = datetime.now(timezone.utc).isoformat()
    now_date = now_iso.split('T')[0] # Date part only for template replacement

    # Mock mode check
    if state.get('mock_llm'):
        print("--- INFO: Tech Lead operando em modo MOCK. Carregando especificação técnica e validação pré-definidas. ---")
        
        # Process MOCK_TL_VALIDATION_RESULT
        validation_result_mock = MOCK_TL_VALIDATION_RESULT
        if validation_result_mock["needs_feedback"]:
            print(f"--- Tech Lead (MOCK): Feedback para o Product Manager ---")
            state['pm_feedback'] = validation_result_mock["feedback_message"]
            state[str(StateKey.NEXT_AGENT)] = Agent.PRODUCT_MANAGER.value
            print(f"--- INFO: Feedback enviado ao PM (MOCK): {validation_result_mock['feedback_message']} ---")
            return state
        else:
            print(f"--- Tech Lead (MOCK): User Stories aprovadas: {validation_result_mock['feedback_message']} ---")
            state['pm_feedback'] = None # Clear any previous feedback

            # Process MOCK_TL_TECH_SPEC_DATA
            generated_tech_spec = MOCK_TL_TECH_SPEC_DATA
            
            # Extract epic_id from user stories if available, for filename
            user_stories_for_mock = state.get('user_stories') # Use user_stories from state for mock
            epic_id = user_stories_for_mock[0]['epic_id'] if user_stories_for_mock else "UNKNOWN"
            tech_spec_id = f"{epic_id}-TS001" # Simplistic ID for now

            # Simulate placeholder replacement for the mock tech spec
            generated_tech_spec = generated_tech_spec.replace("[Título da User Story]", f"Especificação Técnica para o Épico {epic_id} (MOCK)")
            generated_tech_spec = generated_tech_spec.replace("[ID da Spec - Ver `id_conventions.json` (tech_spec)]", tech_spec_id)
            generated_tech_spec = generated_tech_spec.replace("[ID da User Story relacionada - ex: US-XXX]", ", ".join([us['id'] for us in user_stories_for_mock]) if user_stories_for_mock else "N/A")
            generated_tech_spec = generated_tech_spec.replace("[Status]", "Draft (MOCK)")
            generated_tech_spec = generated_tech_spec.replace("[Autor]", "Tech Lead Bot (MOCK)")
            generated_tech_spec = generated_tech_spec.replace("[YYYY-MM-DD]", now_date)


            state['tech_spec'] = generated_tech_spec
            
            # Save the generated tech spec to a file (mocked)
            output_dir_mock = state.get('output_dir') # Use a different name to avoid conflict with actual logic
            if output_dir_mock:
                tech_spec_filename = os.path.join(output_dir_mock, f"tech_spec_{tech_spec_id}.md")
                with open(tech_spec_filename, 'w', encoding='utf-8') as f:
                    f.write(generated_tech_spec)
                print(f"--- INFO: Especificação Técnica salva em: {tech_spec_filename} (MOCK) ---")
            
            state[str(StateKey.NEXT_AGENT)] = Agent.DEVELOPER.value # Set next agent in mock mode
            return state
    
    # --- Actual LLM Logic (if not mock_llm) ---
    else:
        llm = get_llm_client(state['llm_provider'], state['llm_model_name'], temperature=0)
        print(f"--- INFO: Tech Lead usando LLM: {state['llm_provider']}/{state['llm_model_name']} ---")

        validation_parser = PydanticOutputParser(pydantic_object=TechLeadValidationResult)
        validation_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", """Você é um Tech Lead experiente e pragmático. Sua tarefa é revisar as User Stories fornecidas pelo Product Manager.
                 Seu objetivo é garantir que as histórias sejam claras, completas e tecnicamente viáveis para que a equipe de desenvolvimento possa iniciar o trabalho sem ambiguidades.

                 **Sua análise deve focar em:**
                 - **Ambiguidade:** Há termos ou conceitos que podem ser interpretados de diferentes formas?
                 - **Requisitos Faltantes:** Há informações cruciais para a implementação que não estão explícitas (ex: validações, formatos de dados, integrações, requisitos não funcionais)?
                 - **Testabilidade:** Os critérios de aceitação são claros e mensuráveis? Eles cobrem cenários de sucesso e falha?

                 **Formato do Feedback (se `needs_feedback` for `true`):**
                 - Seja específico e objetivo.
                 - Indique a User Story (ex: E-001-US001) quando aplicável.
                 - Apresente o feedback em tópicos ou perguntas claras que o Product Manager possa usar para refinar a história ou buscar mais informações.
                 - Exemplo: "US001 (Cadastro): Qual o formato esperado para o CEP? Há validação?"

                 **Formato do Feedback (se `needs_feedback` for `false`):**
                 - Uma mensagem clara de aprovação, indicando que as User Stories estão prontas para a especificação técnica.

                 {format_instructions}
                 """),
                ("human", "Revise as seguintes User Stories:\n{user_stories}\n\nCom base na sua análise, as User Stories estão prontas para a especificação técnica ou o Product Manager precisa fornecer mais feedback?"),
            ]
        ).partial(format_instructions=validation_parser.get_format_instructions())

        tech_spec_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Você é um Tech Lead experiente e arquiteto de software. Sua tarefa é criar uma Especificação Técnica detalhada com base nas User Stories aprovadas. Use o template fornecido e preencha todas as seções de forma concisa e completa. Seja o mais técnico possível, mas compreensível. O template a ser seguido é:\n\n{tech_spec_template}\n\nCertifique-se de que cada User Story seja abordada na especificação."),
                ("human", "Crie uma especificação técnica para as seguintes User Stories:\n{user_stories}"),
            ]
        )

        validation_chain = validation_prompt | llm | validation_parser
        
        user_stories_str = "\n".join([json.dumps(us) for us in state['user_stories']])

        try:
            print("--- INFO: Validando User Stories com o LLM... ---")
            validation_result = validation_chain.invoke({"user_stories": user_stories_str})

            if validation_result.needs_feedback:
                print(f"--- AVISO: Tech Lead precisa de feedback. Parametrizando dúvidas e prosseguindo para o Developer. ---")
                state['tech_lead_feedback'] = f"Feedback parametrizado pelo TL: {validation_result.feedback_message}"
                state['pm_feedback'] = None # Clear PM feedback
                state['tech_spec'] = "Especificação Técnica básica gerada com base em User Stories parametrizadas (feedback não resolvido)." # Set placeholder tech_spec
                state[str(StateKey.NEXT_AGENT)] = Agent.DEVELOPER.value
                return state
            else:
                print(f"--- Tech Lead: User Stories aprovadas: {validation_result.feedback_message} ---")
                state['pm_feedback'] = None # Clear any previous feedback

                print("--- INFO: Gerando Especificação Técnica com o LLM... ---")
                tech_spec_chain = tech_spec_prompt | llm
                generated_tech_spec = tech_spec_chain.invoke({"user_stories": user_stories_str, "tech_spec_template": TECH_SPEC_TEMPLATE_CONTENT}).content

                state['tech_spec'] = generated_tech_spec
                
                # Save the generated tech spec to a file
                output_dir = state.get('output_dir')
                if output_dir:
                    # Determine a simple tech spec ID. In a real system, this would be more robust.
                    # Assuming user_stories is a list of dicts, get the epic_id from the first one.
                    epic_id = state['user_stories'][0]['epic_id'] if state['user_stories'] else "UNKNOWN_EPIC"
                    
                    # Generate a timestamp for uniqueness
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    tech_spec_filename = os.path.join(output_dir, f"tech_spec_{epic_id}_{timestamp}.md")
                    
                    with open(tech_spec_filename, 'w', encoding='utf-8') as f:
                        f.write(generated_tech_spec)
                    print(f"--- INFO: Especificação Técnica salva em: {tech_spec_filename} ---")
                
                state[str(StateKey.NEXT_AGENT)] = Agent.DEVELOPER.value
                return state

        except Exception as e:
            print(f"--- ERRO NO NÓ TECH LEAD: {e} ---")
            state['error'] = f"Tech Lead Node Error: {e}"
            state[str(StateKey.NEXT_AGENT)] = Agent.CTO.value # Escalate to CTO or a "Error Handling" agent
            return state