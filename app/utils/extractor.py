import sys
import os

# Este bloque asegura que se pueda importar auto_train sin errores
current_dir = os.path.dirname(os.path.abspath(__file__))  # app/utils
auto_train_path = os.path.abspath(os.path.join(current_dir, "..", "auto_train"))
if auto_train_path not in sys.path:
    sys.path.insert(0, auto_train_path)

import pandas as pd
import re
from io import BytesIO
import json  # Para json.dumps
from ruamel.yaml import YAML
from rapidfuzz import fuzz
from auto_train.loader import BotFlowLoader


def normalize(text: str) -> str:
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


def extract_entity_data_from_nlu_block(
    nlu_data_block: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extrae las declaraciones de entidades (instances) y las definiciones de tipos de entidad
    del bloque NLU proporcionado.
    """
    # --- DEBUGGING START (extractor.py) ---
    print(
        "\n--- DEBUG (extractor.py): Entrando a extract_entity_data_from_nlu_block ---"
    )
    if isinstance(nlu_data_block, dict):
        print(f"Keys in nlu_data_block: {list(nlu_data_block.keys())}")
        if "entities" in nlu_data_block:
            print(
                f"Content of 'entities' (primeros 2 si existen): {nlu_data_block['entities'][:2]}"
            )
        else:
            print("'entities' key NOT FOUND in nlu_data_block")
        if "entityTypes" in nlu_data_block:
            print(
                f"Content of 'entityTypes' (primeros 2 si existen): {nlu_data_block['entityTypes'][:2]}"
            )
        else:
            print("'entityTypes' key NOT FOUND in nlu_data_block")
    else:
        print(f"nlu_data_block NO es un dict. Tipo: {type(nlu_data_block)}")
    print("--- DEBUG (extractor.py): Fin inspección nlu_data_block ---\n")
    # --- DEBUGGING END (extractor.py) ---

    entity_declarations_list = []
    entity_type_definitions_list = []

    if not nlu_data_block or not isinstance(nlu_data_block, dict):
        return pd.DataFrame(columns=["entity_name", "entity_type_ref"]), pd.DataFrame(
            columns=[
                "entity_type_name",
                "entity_type_description",
                "item_value",
                "item_synonyms",
            ]
        )

    # 1. Extraer Entity Declarations (instances)
    raw_entity_declarations = nlu_data_block.get("entities", [])
    if raw_entity_declarations:
        for entity_instance in raw_entity_declarations:
            entity_declarations_list.append(
                {
                    "entity_name": entity_instance.get("name"),
                    "entity_type_ref": entity_instance.get("type"),
                }
            )
    df_entity_declarations = pd.DataFrame(entity_declarations_list)
    if df_entity_declarations.empty:
        df_entity_declarations = pd.DataFrame(
            columns=["entity_name", "entity_type_ref"]
        )

    # 2. Extraer Entity Type Definitions
    raw_entity_type_definitions = nlu_data_block.get("entityTypes", [])
    if raw_entity_type_definitions:
        for etype_def in raw_entity_type_definitions:
            etype_name = etype_def.get("name")
            etype_description = etype_def.get("description", "")
            mechanism = etype_def.get("mechanism", {})

            if mechanism.get("type") == "List":
                items = mechanism.get("items", [])
                if not items:  # Si es un tipo Lista pero no tiene items
                    entity_type_definitions_list.append(
                        {
                            "entity_type_name": etype_name,
                            "entity_type_description": etype_description,
                            "item_value": pd.NA,
                            "item_synonyms": pd.NA,
                        }
                    )
                else:
                    for item in items:
                        item_value = item.get("value")
                        item_synonyms_list = item.get("synonyms", [])
                        item_synonyms_json = (
                            json.dumps(item_synonyms_list)
                            if item_synonyms_list
                            else pd.NA
                        )
                        entity_type_definitions_list.append(
                            {
                                "entity_type_name": etype_name,
                                "entity_type_description": etype_description,
                                "item_value": item_value,
                                "item_synonyms": item_synonyms_json,
                            }
                        )
            else:  # Otros tipos de entidad (no lista) o sin mecanismo detallado
                entity_type_definitions_list.append(
                    {
                        "entity_type_name": etype_name,
                        "entity_type_description": etype_description,
                        "item_value": pd.NA,  # Usar pd.NA para valores faltantes
                        "item_synonyms": pd.NA,
                    }
                )
    df_entity_type_definitions = pd.DataFrame(entity_type_definitions_list)
    if df_entity_type_definitions.empty:
        df_entity_type_definitions = pd.DataFrame(
            columns=[
                "entity_type_name",
                "entity_type_description",
                "item_value",
                "item_synonyms",
            ]
        )

    # --- DEBUGGING START (extractor.py) ---
    print("\n--- DEBUG (extractor.py): DataFrames generados internamente ---")
    print(f"df_entity_declarations (head):\n{df_entity_declarations.head()}")
    print(f"df_entity_declarations empty?: {df_entity_declarations.empty}")
    print(f"df_entity_type_definitions (head):\n{df_entity_type_definitions.head()}")
    print(f"df_entity_type_definitions empty?: {df_entity_type_definitions.empty}")
    print("--- DEBUG (extractor.py): Fin DataFrames generados ---\n")
    # --- DEBUGGING END (extractor.py) ---

    return df_entity_declarations, df_entity_type_definitions


def extract_intents(
    yaml_bytes: bytes,
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:  # Added df_intent_details
    flow = BotFlowLoader.load_from_bytes(yaml_bytes)

    # Parsear el YAML completo una vez para acceder a los IDs de intención directamente
    yaml_parser = YAML(typ="safe")
    try:
        yaml_content_str = yaml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        yaml_content_str = yaml_bytes.decode("latin-1", errors="replace")

    full_yaml_data = yaml_parser.load(yaml_content_str)

    intent_name_to_id_map = {}
    if isinstance(full_yaml_data, dict) and "botFlow" in full_yaml_data:
        bot_flow_data = full_yaml_data.get("botFlow", {})
        nlu_data_block_for_ids = bot_flow_data.get(
            "settingsNaturalLanguageUnderstanding", {}
        ).get("nluDomainVersion", {})

        if nlu_data_block_for_ids and "intents" in nlu_data_block_for_ids:
            for intent_data_from_yaml in nlu_data_block_for_ids["intents"]:
                if "name" in intent_data_from_yaml and "id" in intent_data_from_yaml:
                    intent_name_to_id_map[intent_data_from_yaml["name"]] = (
                        intent_data_from_yaml["id"]
                    )

    utterances_list = []
    intent_details_list = []
    processed_intent_ids = set()  # To store unique intent_name and intent_id

    for intent_obj in flow.get_intents():
        intent_name_val = intent_obj.name
        # Obtener el ID de la intención del mapa creado a partir del parseo directo del YAML
        intent_id_val = intent_name_to_id_map.get(intent_name_val)

        # Store unique intent details (name and ID)
        if (
            intent_id_val and intent_id_val not in processed_intent_ids
        ):  # Solo si se encontró un ID
            intent_details_list.append(
                {"intent_name": intent_name_val, "intent_id": intent_id_val}
            )
            processed_intent_ids.add(intent_id_val)

        for utt_obj in intent_obj.utterances:  # utt_obj is an Utterance object
            raw_text = utt_obj.text
            original_id = utt_obj.id
            original_segments = utt_obj.segments  # Obtener los segmentos originales

            # Extraer nombres de entidades (slots) de los segmentos
            slots_found = []
            if original_segments and isinstance(original_segments, list):
                for segment in original_segments:
                    if isinstance(segment, dict):
                        entity_data = segment.get("entity")
                        if isinstance(entity_data, dict):
                            entity_name = entity_data.get("name")
                            if entity_name:
                                slots_found.append(entity_name)
            # Unir nombres de slots únicos, si se encontraron
            slots_str = (
                ", ".join(sorted(list(set(slots_found)))) if slots_found else None
            )

            utterances_list.append(
                {
                    "intent_name": intent_name_val,  # For reference and potential joining
                    "intent_id": (
                        intent_id_val if intent_id_val else str(uuid.uuid4())
                    ),  # Fallback a nuevo UUID si no se encontró ID
                    "utterance_text": raw_text,
                    "utterance_id": original_id,  # Store the original ID
                    "slots": slots_str,  # Nueva columna con los nombres de las entidades
                    "segments_original": (
                        json.dumps(original_segments) if original_segments else None
                    ),  # Guardar como JSON
                    # "norm" column for find_duplicates will be derived later
                }
            )

    df_utterances_output = pd.DataFrame(utterances_list)
    df_intent_details = pd.DataFrame(intent_details_list)

    # Prepare DataFrame for find_duplicates function
    if not df_utterances_output.empty:
        # find_duplicates expects columns 'intent' and 'utterance'
        df_for_duplicates = df_utterances_output.rename(
            columns={"intent_name": "intent", "utterance_text": "utterance"}
        )[["intent", "utterance"]].copy()
        # 'norm' is added inside find_duplicates
    else:
        df_for_duplicates = pd.DataFrame(columns=["intent", "utterance"])

    df_dups = find_duplicates(df_for_duplicates, threshold=90)

    # Renombrar columnas para la salida esperada por streamlit_app.py
    # df_utterances_output already has the desired column names ('intent_name', 'utterance_text', etc.)
    # No specific renaming needed here for these primary columns if constructed directly with target names.
    # Ensure 'norm' is not in df_utterances_output if it was temporarily added.
    # (It's not added to utterances_list directly in this version, so .drop not needed for 'norm')

    # Extraer datos de entidades usando el full_yaml_data ya parseado
    nlu_data_block = {}  # Inicializar

    # Ajuste para acceder correctamente al bloque NLU anidado
    if isinstance(full_yaml_data, dict) and "botFlow" in full_yaml_data:
        bot_flow_data = full_yaml_data.get("botFlow", {})
        nlu_data_block = bot_flow_data.get(
            "settingsNaturalLanguageUnderstanding", {}
        ).get("nluDomainVersion", {})
    else:  # Si no hay 'botFlow' o full_yaml_data no es un dict, nlu_data_block será vacío
        nlu_data_block = {}

    df_entity_declarations, df_entity_type_definitions = (
        extract_entity_data_from_nlu_block(nlu_data_block)
    )

    return (
        df_utterances_output,  # Renamed from df_intents_output
        df_dups,
        df_entity_declarations,
        df_entity_type_definitions,
        df_intent_details,  # New DataFrame with intent names and IDs
    )


def find_duplicates(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    df = df.assign(norm=df["utterance"].map(normalize))
    counts = df["norm"].value_counts()
    exact_norms = counts[counts > 1].index
    exact_df = df[df["norm"].isin(exact_norms)].copy()
    exact_df["similarity"] = 100
    exact_df["type"] = "duplicado"
    exact_df["mismo_intent"] = exact_df.groupby("norm")["intent"].transform(
        lambda x: len(x.unique()) == 1
    )
    # Agrupar los intents únicos por cada utterance normalizado
    intent_groups = (
        df.groupby("norm")["intent"].unique().apply(lambda x: ", ".join(sorted(set(x))))
    )

    # exactos
    exact_df = df[df["norm"].duplicated(keep=False)].copy()
    exact_df["similarity"] = 100
    exact_df["type"] = "duplicado"
    exact_df["mismo_intent"] = exact_df["norm"].map(
        lambda n: len(set(df[df["norm"] == n]["intent"])) == 1
    )
    exact_df["intents"] = exact_df["norm"].map(intent_groups)
    exact_out = exact_df[["utterance", "intents", "similarity", "type", "mismo_intent"]]

    uniq = list(set(df["norm"]) - set(exact_norms))
    approx_rows = []
    for i, n1 in enumerate(uniq):
        for n2 in uniq[i + 1 :]:
            score = fuzz.ratio(n1, n2)
            if threshold <= score < 100:
                sample1 = df[df["norm"] == n1].iloc[0]
                sample2 = df[df["norm"] == n2].iloc[0]
                intents1 = ",".join(df[df["norm"] == n1]["intent"].unique())
                intents2 = ",".join(df[df["norm"] == n2]["intent"].unique())
                same_intent = intents1 == intents2
                approx_rows.append(
                    {
                        "utterance": sample1.utterance,
                        "intents": intents1,
                        "similarity": score,
                        "type": "aproximado",
                        "mismo_intent": same_intent,
                    }
                )
                approx_rows.append(
                    {
                        "utterance": sample2.utterance,
                        "intents": intents2,
                        "similarity": score,
                        "type": "aproximado",
                        "mismo_intent": same_intent,
                    }
                )

    approx_out = pd.DataFrame(approx_rows).drop_duplicates()
    return pd.concat([exact_out, approx_out], ignore_index=True)
