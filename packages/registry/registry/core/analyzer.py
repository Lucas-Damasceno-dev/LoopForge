"""Analisador de Breaking Changes em assinaturas de interface."""

from datetime import datetime, timezone
from typing import List, Tuple
from registry.store.models import BreakingChange, InterfaceItem, RegistrySchema


def analyze_signature_change(old_sig: str, new_sig: str) -> Tuple[bool, str, str]:
    """Retorna (is_breaking, change_type, details)."""
    if old_sig == new_sig:
        return False, "no_change", "Nenhuma alteração"

    # Extrair parâmetros entre parênteses
    def parse_params(sig: str) -> List[str]:
        if "(" in sig and ")" in sig:
            inside = sig[sig.find("(") + 1 : sig.rfind(")")]
            if not inside.strip():
                return []
            return [p.strip() for p in inside.split(",") if p.strip()]
        return []

    old_params = parse_params(old_sig)
    new_params = parse_params(new_sig)

    # Caso 1: Parâmetro removido
    if len(new_params) < len(old_params):
        return True, "parameter_removed", f"Parâmetro(s) removido(s): {len(old_params)} -> {len(new_params)}"

    # Caso 2: Parâmetro adicionado
    if len(new_params) > len(old_params):
        # Verificar se novos parâmetros têm valor padrão (ex: `discount: float = 0.0` ou `discount?: float`)
        added = new_params[len(old_params) :]
        has_required = any("=" not in p and "?" not in p for p in added)
        if has_required:
            return True, "parameter_added_without_default", f"Parâmetro obrigatório adicionado sem valor padrão: {added}"
        else:
            return False, "additive_change", f"Parâmetro opcional adicionado: {added}"

    # Caso 3: Mesmo número de parâmetros, mas tipos ou nomes alterados
    if old_params != new_params:
        return True, "signature_changed", f"Assinatura alterada de '{old_sig}' para '{new_sig}'"

    return False, "no_change", "Nenhuma alteração de quebra"


def check_breaking_changes(old_schema: RegistrySchema, new_schema: RegistrySchema) -> List[BreakingChange]:
    old_map = {item.id: item for item in old_schema.interfaces}
    breaking: List[BreakingChange] = []

    now_iso = datetime.now(timezone.utc).isoformat()

    for new_item in new_schema.interfaces:
        if new_item.id in old_map:
            old_item = old_map[new_item.id]
            is_breaking, change_type, details = analyze_signature_change(old_item.signature, new_item.signature)

            if is_breaking:
                breaking.append(
                    BreakingChange(
                        interface_id=new_item.id,
                        interface_name=new_item.name,
                        module=new_item.module,
                        change_type=change_type,
                        details=details,
                        impacted_consumers=old_item.consumers,
                        detected_at=now_iso,
                    )
                )

    return breaking
