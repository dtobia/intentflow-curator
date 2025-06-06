import pandas as pd
from ruamel.yaml import YAML
import os
import re
from io import StringIO
import uuid
import json  # Para cargar segments_original
import copy

# Intentar importar BotFlowLoader. Asumimos que sys.path está configurado
# correctamente por el script principal (streamlit_app.py) o la estructura del proyecto.
try:
    from auto_train.loader import BotFlowLoader
except ImportError:
    # Fallback o manejo de error si es necesario, aunque idealmente el path está bien.
    print(
        "Warning: BotFlowLoader could not be imported in builder.py. ID preservation from original YAML might fail."
    )
    BotFlowLoader = None


# Copiamos la función normalize para evitar dependencias directas con extractor.py
# y para asegurar su disponibilidad aquí.
def normalize_for_builder(text: str) -> str:
    if not isinstance(text, str):  # Manejar datos que no sean string
        return ""
    t = text.strip().lower()
    t = (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    t = re.sub(r"[¿\?¡!.,;:]+", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def build_nlu_yaml_block(
    df_utterances: pd.DataFrame,
    df_intent_details: pd.DataFrame,
    original_utterance_ids_map: dict,
):
    """
    Construye el bloque NLU (solo la parte de 'settingsNaturalLanguageUnderstanding')
    basado en los DataFrames de enunciados y detalles de intenciones.
    """
    block = {
        "settingsNaturalLanguageUnderstanding": {
            "nluDomainVersion": {
                "intents": [],
                "entities": [],
                "entityTypes": [],
                "language": "es-us",
                "languageVersions": {},
            },
            "mutedUtterances": [],
        }
    }

    # Crear un mapeo de nombre de intención a ID de intención desde df_intent_details
    # Asegurarse que las columnas en df_intent_details se llamen 'intent_name' e 'intent_id'
    intent_id_map = pd.Series(
        df_intent_details.intent_id.values, index=df_intent_details.intent_name
    ).to_dict()

    # df_utterances ya tiene las columnas renombradas a 'intent' y 'utterance'
    # por streamlit_app.py antes de llamar a esta función.
    # También debería tener 'utterance_id', 'segments_original'.

    for intent_name_from_excel, group in df_utterances.groupby(
        "intent"
    ):  # 'intent' es la columna con el nombre de la intención
        utterances_for_intent = []

        # Obtener el ID original de la intención usando el nombre de la intención
        intent_id_to_use = intent_id_map.get(intent_name_from_excel)

        if not intent_id_to_use:
            print(
                f"ADVERTENCIA: La intención '{intent_name_from_excel}' de la hoja 'utterances' no se encontró en la hoja 'intents'. Se generará un nuevo ID para la intención."
            )
            intent_id_to_use = str(uuid.uuid4())

        for _, row in group.iterrows():
            utterance_text = row["utterance"]
            utterance_id_excel = row.get("utterance_id")
            segments_original_str = row.get("segments_original")

            # Lógica para los segmentos del utterance
            segments = []
            if (
                segments_original_str
                and isinstance(segments_original_str, str)
                and segments_original_str.strip()
            ):
                try:
                    parsed_segments = json.loads(segments_original_str)
                    if isinstance(parsed_segments, list) and all(
                        isinstance(s, dict) for s in parsed_segments
                    ):
                        segments = parsed_segments
                    else:
                        # print(f"Advertencia: segments_original para '{utterance_text}' no es una lista de diccionarios válida. Usando texto plano.")
                        segments = [{"text": utterance_text}]
                except json.JSONDecodeError:
                    # print(f"Advertencia: JSONDecodeError en segments_original para '{utterance_text}'. Usando texto plano.")
                    segments = [{"text": utterance_text}]
            else:
                segments = [{"text": utterance_text}]

            if not segments:  # Asegurar que segments nunca esté vacío
                segments = [{"text": utterance_text}]

            # Lógica para el ID del utterance
            final_utterance_id = None
            if (
                utterance_id_excel
                and pd.notna(utterance_id_excel)
                and str(utterance_id_excel).strip()
            ):
                final_utterance_id = str(utterance_id_excel)
            else:
                norm_text = normalize_for_builder(utterance_text)
                if norm_text in original_utterance_ids_map:
                    final_utterance_id = original_utterance_ids_map[norm_text]

            if not final_utterance_id:
                final_utterance_id = str(uuid.uuid4())

            utterances_for_intent.append(
                {
                    "segments": segments,
                    "id": final_utterance_id,
                    "source": "User",
                }
            )

        intent_data = {
            "utterances": utterances_for_intent,
            "entityNameReferences": [],
            "id": intent_id_to_use,  # Usar el ID de la intención original/especificado
            "name": intent_name_from_excel,
        }

        # Aquí podrías añadir la descripción de la intención si la tienes en df_intent_details
        # Ejemplo:
        # intent_description = df_intent_details[df_intent_details['intent_name'] == intent_name_from_excel]['description'].iloc[0]
        # if pd.notna(intent_description):
        #    intent_data["description"] = intent_description

        block["settingsNaturalLanguageUnderstanding"]["nluDomainVersion"][
            "intents"
        ].append(intent_data)

    return block


def get_original_utterance_ids_map_from_yaml_bytes(yaml_bytes: bytes) -> dict:
    if not yaml_bytes or not BotFlowLoader:
        return {}
    try:
        flow = BotFlowLoader.load_from_bytes(yaml_bytes)
        id_map = {}
        for intent_obj in flow.get_intents():
            for utt_obj in intent_obj.utterances:
                if isinstance(utt_obj.text, str) and utt_obj.id:
                    norm_text = normalize_for_builder(utt_obj.text)
                    if (
                        norm_text not in id_map
                    ):  # Priorizar el primer ID encontrado para un texto normalizado
                        id_map[norm_text] = utt_obj.id
        return id_map
    except Exception as e:
        print(f"Error al parsear YAML original para IDs en builder.py: {e}")
        return {}


def build_yaml(
    df_utterances: pd.DataFrame,  # Renombrado de df_intents
    df_intent_details: pd.DataFrame,  # Nuevo DataFrame con detalles de intenciones
    original_yaml_content_for_ids: bytes = None,
) -> str:
    """
    Construye la representación en string YAML del bloque NLU.
    """
    original_utterance_ids_map = {}
    if original_yaml_content_for_ids:
        original_utterance_ids_map = get_original_utterance_ids_map_from_yaml_bytes(
            original_yaml_content_for_ids
        )

    # La función build_nlu_yaml_block ahora toma los DataFrames directamente
    nlu_yaml_block_dict = build_nlu_yaml_block(
        df_utterances, df_intent_details, original_utterance_ids_map
    )

    yaml = YAML()
    # yaml.preserve_quotes = True # Puede causar problemas con strings multilínea si no se maneja con cuidado
    yaml.preserve_quotes = True
    yaml.default_style = '"'  # Forzar comillas dobles para strings escalares simples.
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096  # prevenir cortes de línea
    stream = StringIO()
    yaml.dump(nlu_yaml_block_dict, stream)
    return stream.getvalue()


# ✅ merge_into_original sin el pop innecesario
def merge_into_original(original_yaml_bytes: bytes, new_nlu_block: dict) -> str:
    yaml = YAML()
    yaml.preserve_quotes = True
    # yaml.default_flow_style = False # Comentado para permitir que ruamel decida, puede mejorar legibilidad
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096

    original_data = yaml.load(original_yaml_bytes)

    if "botFlow" not in original_data:
        raise KeyError("El YAML original no contiene 'botFlow'")

    # Acceder al bloque NLU del YAML original
    original_bot_flow = original_data.get("botFlow", {})
    original_nlu_settings = original_bot_flow.get(
        "settingsNaturalLanguageUnderstanding", {}
    )
    original_nlu_domain_version = original_nlu_settings.get("nluDomainVersion", {})

    # Obtener entidades y tipos de entidad del YAML original para preservarlos
    # (Asumiendo que no se modifican a través del Excel en este flujo)
    preserved_entities = original_nlu_domain_version.get("entities", [])
    preserved_entity_types = original_nlu_domain_version.get("entityTypes", [])
    preserved_language = original_nlu_domain_version.get(
        "language", "es-us"
    )  # Preservar idioma
    preserved_language_versions = original_nlu_domain_version.get(
        "languageVersions", {}
    )  # Preservar versiones

    # Obtener el nuevo bloque de intenciones del NLU generado
    new_nlu_settings_from_block = new_nlu_block.get(
        "settingsNaturalLanguageUnderstanding", {}
    )
    new_nlu_domain_version_from_block = new_nlu_settings_from_block.get(
        "nluDomainVersion", {}
    )
    new_intents_list = new_nlu_domain_version_from_block.get("intents", [])

    # Reconstruir el nluDomainVersion con las nuevas intenciones y las entidades/tipos preservados
    final_nlu_domain_version = {
        "intents": new_intents_list,
        "entities": preserved_entities,
        "entityTypes": preserved_entity_types,
        "language": preserved_language,
        "languageVersions": preserved_language_versions,
    }

    # Reinsertar entityNameReferences y description si existen en el original
    # y el intent_name coincide
    if "intents" in original_nlu_domain_version:
        for orig_intent_data in original_nlu_domain_version.get("intents", []):
            tgt = next(
                (
                    intent_dict
                    for intent_dict in final_nlu_domain_version["intents"]
                    if intent_dict.get("name") == orig_intent_data.get("name")
                ),
                None,
            )
            if tgt:
                if "entityNameReferences" in orig_intent_data:
                    tgt["entityNameReferences"] = orig_intent_data[
                        "entityNameReferences"
                    ]
                if (
                    "description" in orig_intent_data and "description" not in tgt
                ):  # Solo si no se puso desde Excel
                    tgt["description"] = orig_intent_data["description"]

    # Actualizar el bloque NLU en la estructura de datos original
    original_data["botFlow"]["settingsNaturalLanguageUnderstanding"][
        "nluDomainVersion"
    ] = final_nlu_domain_version
    # Preservar mutedUtterances si existe en el original
    if "mutedUtterances" in original_nlu_settings:
        original_data["botFlow"]["settingsNaturalLanguageUnderstanding"][
            "mutedUtterances"
        ] = original_nlu_settings["mutedUtterances"]

    stream = StringIO()
    yaml.dump(original_data, stream)
    return stream.getvalue()
