import os
import glob
import pandas as pd
from collections import defaultdict


def load_intents_from_multiple_excels(folder_path):
    file_pattern = os.path.join(folder_path, "step1_intent_output_*.xlsx")
    excel_files = glob.glob(file_pattern)

    intents = defaultdict(list)
    for file_path in excel_files:
        df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            intent = str(row["Intent"]).strip()
            utterance = str(row["Utterance"]).strip()
            if intent and utterance:
                intents[intent].append(utterance)
    return intents


from ruamel.yaml import YAML
from io import BytesIO


class Intent:
    def __init__(self, name, utterances):
        self.name = name
        self.utterances = [Utterance(u) for u in utterances]


class Utterance:
    def __init__(self, utterance_obj_from_yaml):
        if isinstance(utterance_obj_from_yaml, dict):
            self.segments = utterance_obj_from_yaml.get("segments", [{"text": ""}]) # Guardar lista de segmentos
            self.text = " ".join(seg.get("text", "") for seg in self.segments) # Texto concatenado para visualización/edición simple
            self.id = utterance_obj_from_yaml.get("id")
        else:
            self.text = utterance_obj_from_yaml  # fallback for simple text
            self.segments = [{"text": str(utterance_obj_from_yaml)}] # Estructura de segmento simple para fallback
            self.id = None


class BotFlowLoader:
    @staticmethod
    def load_from_bytes(yaml_bytes: bytes):
        yaml = YAML()
        data = yaml.load(BytesIO(yaml_bytes))

        # Soportar estructuras tipo "botFlow -> settingsNaturalLanguageUnderstanding"
        snlu = None
        if "settingsNaturalLanguageUnderstanding" in data:
            snlu = data["settingsNaturalLanguageUnderstanding"]
        elif (
            "botFlow" in data
            and "settingsNaturalLanguageUnderstanding" in data["botFlow"]
        ):
            snlu = data["botFlow"]["settingsNaturalLanguageUnderstanding"]

        if (
            not snlu
            or "nluDomainVersion" not in snlu
            or "intents" not in snlu["nluDomainVersion"]
        ):
            raise ValueError("No se encontró la sección intents del NLU en el YAML")

        raw_intents = snlu["nluDomainVersion"]["intents"]
        return BotFlow(raw_intents)


class BotFlow:
    def __init__(self, raw_intents):
        self.intents = [Intent(i["name"], i["utterances"]) for i in raw_intents]

    def get_intents(self):
        return self.intents
