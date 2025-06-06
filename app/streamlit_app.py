import streamlit as st
import pandas as pd
import io
import os
from utils.extractor import extract_intents
from utils.builder import build_yaml
from utils.builder import merge_into_original
from ruamel.yaml import YAML
from io import StringIO
import copy

# import streamlit as st # Streamlit ya se importa una vez al inicio
import hashlib
import json  # Para cargar archivos JSON


# --- Internacionalización (i18n) ---
LANGUAGES_DIR = os.path.join(os.path.dirname(__file__), "locales")
AVAILABLE_LANGUAGES = {"es": "Español", "en": "English"}
DEFAULT_LANGUAGE = "es"


# Función auxiliar para cargar el título inicial sin usar comandos de Streamlit
# que dependan del estado de la sesión completamente inicializado por main().
def _get_initial_page_title(  # Actualizado el fallback_title
    lang_code=DEFAULT_LANGUAGE, fallback_title="IntentFlow Curator"
):  # Actualizado el fallback_title
    """
    Carga app_title desde el archivo JSON del idioma especificado.
    Esta función está pensada para ser usada por st.set_page_config y NO debe llamar
    a otros comandos de Streamlit como st.error o st.session_state directamente si aún no están listos.
    """
    try:
        path = os.path.join(LANGUAGES_DIR, f"{lang_code}.json")
        with open(path, "r", encoding="utf-8") as f:
            translations = json.load(f)
        return translations.get("app_title", fallback_title)
    except Exception:
        return fallback_title


# Llamar a st.set_page_config() UNA VEZ, como el primer comando de Streamlit.
st.set_page_config(page_title=_get_initial_page_title(), layout="wide")


@st.cache_data  # Cachear la carga de traducciones
def load_translations(language_code):
    """Carga las traducciones para un idioma dado desde un archivo JSON."""
    path = os.path.join(LANGUAGES_DIR, f"{language_code}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(
            f"Archivo de traducción no encontrado: {path}. Usando idioma por defecto."
        )
        if (
            language_code != DEFAULT_LANGUAGE
        ):  # Evitar recursión infinita si el default falta
            return load_translations(DEFAULT_LANGUAGE)
        return {}  # Devuelve un diccionario vacío si el archivo default también falta


def t(key, **kwargs):
    """Devuelve la cadena traducida para la clave dada."""
    lang_code = st.session_state.get("language", DEFAULT_LANGUAGE)

    # Las traducciones se cargan una vez y se almacenan en session_state dentro de main()
    # o cuando cambia el idioma. Aquí solo las usamos.
    current_translations = st.session_state.get(f"translations_{lang_code}", {})

    translation = current_translations.get(key)
    if translation is None:
        # Fallback al idioma por defecto si la clave no está en el idioma actual
        # y el idioma actual no es el por defecto.
        if lang_code != DEFAULT_LANGUAGE:
            default_translations = st.session_state.get(
                f"translations_{DEFAULT_LANGUAGE}", {}
            )
            translation = default_translations.get(
                key, key
            )  # Fallback a la clave misma
        else:
            translation = key  # Fallback a la clave misma si está en el idioma por defecto y no se encuentra

    return translation.format(**kwargs) if isinstance(translation, str) else key


# Función simple para hashear la contraseña
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Diccionario de usuarios:usuario -> contraseña (hash)
USER_CREDENTIALS = {
    "admin": hash_password("AutoTrain1"),
    "admin2": hash_password("AutoTrain2"),
    # Podés agregar más usuarios aquí
}


def login():
    st.title(t("login_title"))
    username = st.text_input(t("username_label"))
    password = st.text_input(t("password_label"), type="password")

    if st.button(t("login_button")):
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == hash_password(
            password
        ):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(t("login_error"))


def main():
    # Inicializar y cargar idioma en el estado de la sesión si no está presente
    if "language" not in st.session_state:
        st.session_state.language = DEFAULT_LANGUAGE

    # Cargar traducciones para el idioma actual si aún no están cargadas
    current_lang_code = st.session_state.language
    if f"translations_{current_lang_code}" not in st.session_state:
        st.session_state[f"translations_{current_lang_code}"] = load_translations(
            current_lang_code
        )
    # Asegurar que las traducciones del idioma por defecto también estén cargadas para fallback
    if (
        DEFAULT_LANGUAGE != current_lang_code
        and f"translations_{DEFAULT_LANGUAGE}" not in st.session_state
    ):
        st.session_state[f"translations_{DEFAULT_LANGUAGE}"] = load_translations(
            DEFAULT_LANGUAGE
        )

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        # Selector de idioma también en la página de login
        # Usar una etiqueta fija bilingüe para el selector inicial
        selected_lang_login = st.selectbox(
            label="Idioma / Language",
            options=list(AVAILABLE_LANGUAGES.keys()),
            format_func=lambda x: AVAILABLE_LANGUAGES[x],
            index=list(AVAILABLE_LANGUAGES.keys()).index(st.session_state.language),
            key="lang_login",
        )
        if selected_lang_login != st.session_state.language:
            st.session_state.language = selected_lang_login
            # Recargar traducciones para el nuevo idioma
            st.session_state[f"translations_{selected_lang_login}"] = load_translations(
                selected_lang_login
            )
            st.rerun()
        login()
        return

    # Selector de idioma en la barra lateral para usuarios autenticados
    with st.sidebar:
        st.title(t("app_title"))  # Título de la sidebar
        selected_lang_sidebar = st.selectbox(
            label=t("language_select_label"),
            options=list(AVAILABLE_LANGUAGES.keys()),
            format_func=lambda x: AVAILABLE_LANGUAGES[x],
            index=list(AVAILABLE_LANGUAGES.keys()).index(st.session_state.language),
            key="lang_sidebar",
        )
        if selected_lang_sidebar != st.session_state.language:
            st.session_state.language = selected_lang_sidebar
            # Recargar traducciones para el nuevo idioma
            st.session_state[f"translations_{selected_lang_sidebar}"] = (
                load_translations(selected_lang_sidebar)
            )
            st.rerun()

    st.title(t("wizard_title"))

    step_labels = [t("nav_step1"), t("nav_step2"), t("nav_step3"), t("nav_step4")]

    if "step" not in st.session_state:
        st.session_state.step = 1

    selected_step = st.radio(
        t("nav_label"),
        options=[1, 2, 3, 4],
        format_func=lambda i: step_labels[i - 1],
        index=st.session_state.step - 1,
        horizontal=True,
    )
    if selected_step != st.session_state.step:
        st.session_state.step = selected_step
        st.rerun()

    if st.session_state.step == 1:
        st.header(t("step1_header"))
        uploaded_yaml = st.file_uploader(
            t("step1_uploader_label"), type=["yaml", "yml"]
        )
        if uploaded_yaml and st.button(t("step1_button_extract")):
            try:
                (
                    df_utterances,
                    df_dups,
                    df_entity_declarations,
                    df_entity_types,
                    df_intent_details,
                ) = extract_intents(uploaded_yaml.read())
                # --- DEBUGGING START ---
                st.write("--- Debug Info: Entity DataFrames ---")
                st.write(
                    "df_entity_declarations (primeras 5 filas):",
                    df_entity_declarations.head(),
                )
                st.write(
                    "df_entity_declarations ¿está vacío?:", df_entity_declarations.empty
                )
                st.write("df_entity_types (primeras 5 filas):", df_entity_types.head())
                st.write("df_entity_types ¿está vacío?:", df_entity_types.empty)
                st.write("--- Debug Info End ---")
                # --- DEBUGGING END ---
                uploaded_yaml.seek(0)
                st.session_state.yaml_original_filename = (
                    uploaded_yaml.name
                )  # Guardar el nombre del archivo
                st.session_state.yaml_original = uploaded_yaml.read()
                st.session_state.df_utterances = (
                    df_utterances  # Renamed from df_intents
                )
                st.session_state.df_dups = df_dups
                st.session_state.df_entity_declarations = df_entity_declarations
                st.session_state.df_entity_types = df_entity_types
                st.session_state.df_intent_details = df_intent_details  # Store new df
                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                st.error(t("step1_error_yaml"))
                st.exception(e)

    elif st.session_state.step == 2:
        st.header(t("step2_header"))
        tabs = st.tabs([t("step2_tab_extracted"), t("step2_tab_duplicates")])
        if st.button(t("step2_button_download_excel")):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                st.session_state.df_utterances.to_excel(  # Use df_utterances
                    writer, sheet_name="utterances", index=False  # Renamed sheet
                )
                st.session_state.df_dups.to_excel(
                    writer, sheet_name="duplicados", index=False
                )
                if (
                    "df_intent_details" in st.session_state
                    and not st.session_state.df_intent_details.empty
                ):
                    st.session_state.df_intent_details.to_excel(
                        writer, sheet_name="intents", index=False
                    )  # New sheet for intent details
                # El paréntesis extra estaba aquí y ha sido eliminado.
                if (
                    "df_entity_declarations" in st.session_state
                    and not st.session_state.df_entity_declarations.empty
                ):
                    st.session_state.df_entity_declarations.to_excel(
                        writer, sheet_name="EntityDeclarations", index=False
                    )
                if (
                    "df_entity_types" in st.session_state
                    and not st.session_state.df_entity_types.empty
                ):
                    st.session_state.df_entity_types.to_excel(
                        writer, sheet_name="EntityTypeDefinitions", index=False
                    )
            output.seek(0)

            # Construir el nombre del archivo Excel dinámicamente
            original_yaml_basename = (
                "Descargar Archivo con Intents"  # Valor por defecto
            )
            if "yaml_original_filename" in st.session_state:
                # Quitar la extensión .yaml o .yml del nombre original
                original_yaml_basename = os.path.splitext(
                    st.session_state.yaml_original_filename
                )[0]

            excel_file_name = f"{original_yaml_basename}_intents.xlsx"

            st.download_button(
                label=t("step2_download_excel_label"),
                data=output,
                file_name=excel_file_name,  # Usar el nombre de archivo dinámico
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with tabs[0]:
            st.subheader(t("step2_subheader_intents_list"))
            edited_df = st.data_editor(
                st.session_state.df_utterances,  # Edit df_utterances
                num_rows="dynamic",
                use_container_width=True,
            )
            st.session_state.df_utterances = edited_df  # Store back to df_utterances

        with tabs[1]:
            st.subheader(t("step2_subheader_duplicates"))

            def highlight_cross_intents(row):
                return [
                    "background-color: #ffd6d6" if row["mismo_intent"] == False else ""
                    for _ in row
                ]

            styled_dups = st.session_state.df_dups.style.apply(
                highlight_cross_intents, axis=1
            )
            st.dataframe(styled_dups, use_container_width=True)

        if st.button(t("step2_button_confirm_curation")):
            st.success(t("step2_success_curation_confirmed"))
            st.session_state.step = 3
            st.rerun()

    elif st.session_state.step == 3:
        st.header(t("step3_header"))

        # Permitir subir/reemplazar el YAML original en el Paso 3
        st.markdown(f"#### {t('step3_subheader_load_yaml')}")
        if "yaml_original" in st.session_state and st.session_state.yaml_original:
            st.info(t("step3_info_yaml_loaded"))
        else:
            st.warning(t("step3_warning_no_yaml"))

        # El uploader debe estar fuera del else para que la variable siempre se defina
        uploaded_original_yaml_step3 = st.file_uploader(
            t("step3_uploader_yaml_label"),
            type=["yaml", "yml"],
            key="yaml_original_uploader_step3",  # Usamos una key específica para este uploader
        )
        if uploaded_original_yaml_step3:
            st.session_state.yaml_original = uploaded_original_yaml_step3.read()
            st.success(t("step3_success_yaml_loaded"))

        st.markdown("---")  # Separador visual
        st.markdown(f"#### {t('step3_subheader_load_excel')}")
        st.markdown(t("step3_markdown_upload_excel"))
        uploaded_excel = st.file_uploader(
            t("step3_uploader_excel_label"), type=["xlsx"]
        )

        if uploaded_excel:
            try:
                # Leer la hoja de enunciados
                df_utterances_excel = pd.read_excel(
                    uploaded_excel, sheet_name="utterances"
                )
                # Asegurarse que la columna utterance_id exista
                if "utterance_id" not in df_utterances_excel.columns:
                    df_utterances_excel["utterance_id"] = None
                # Renombrar columnas para compatibilidad con build_yaml
                if "intent_name" in df_utterances_excel.columns:
                    df_utterances_excel = df_utterances_excel.rename(
                        columns={"intent_name": "intent"}
                    )
                if "utterance_text" in df_utterances_excel.columns:
                    df_utterances_excel = df_utterances_excel.rename(
                        columns={"utterance_text": "utterance"}
                    )
                st.session_state.df_utterances_from_excel = df_utterances_excel

                # Leer la hoja de detalles de intenciones
                df_intent_details_excel = pd.read_excel(
                    uploaded_excel, sheet_name="intents"
                )
                st.session_state.df_intent_details_from_excel = df_intent_details_excel

                st.success(t("step3_success_excel_loaded"))
            except Exception as e:
                st.error(t("step3_error_excel_read"))
                st.exception(e)

        if st.button(t("step3_button_generate_yaml")):
            if (
                "df_utterances_from_excel" not in st.session_state
                or st.session_state.df_utterances_from_excel.empty
            ):
                st.error(t("step3_error_no_intents_data"))
                return
            if (
                "df_intent_details_from_excel" not in st.session_state
                or st.session_state.df_intent_details_from_excel.empty
            ):
                st.error(
                    t("step3_error_no_intent_details_data")
                )  # Nueva clave de traducción necesaria
                return
            if "yaml_original" not in st.session_state:
                st.error(t("step3_error_no_original_yaml"))
            else:
                try:
                    # Convertir string YAML a dict
                    nlu_block_str = build_yaml(
                        df_utterances=st.session_state.df_utterances_from_excel,  # Pasar df_utterances
                        df_intent_details=st.session_state.df_intent_details_from_excel,  # Pasar df_intent_details
                        original_yaml_content_for_ids=st.session_state.yaml_original,
                    )
                    yaml_parser = YAML()
                    nlu_block_dict = yaml_parser.load(nlu_block_str)

                    # Fusionar con YAML original (el de st.session_state.yaml_original)
                    yaml_completo = merge_into_original(
                        st.session_state.yaml_original, nlu_block_dict
                    )

                    # Construir el nombre del archivo YAML de salida dinámicamente para la descarga
                    original_yaml_basename_for_output = (
                        "flow_generated"  # Valor por defecto
                    )
                    if (
                        "yaml_original_filename" in st.session_state
                        and st.session_state.yaml_original_filename
                    ):
                        original_yaml_basename_for_output = os.path.splitext(
                            st.session_state.yaml_original_filename
                        )[0]
                    output_yaml_filename = (
                        f"{original_yaml_basename_for_output}_update.yaml"
                    )

                    # Mostrar botón de descarga
                    st.download_button(
                        label=t("step3_download_yaml_label"),
                        data=yaml_completo,
                        file_name=output_yaml_filename,  # Usar el nombre de archivo dinámico
                        mime="application/x-yaml",
                    )
                except Exception as e:
                    st.error(t("step3_error_generate_yaml"))
                    st.exception(e)
    elif st.session_state.step == 4:
        st.header(t("step4_header"))
        st.markdown(t("step4_markdown_upload_yaml"))
        yaml_uploaded = st.file_uploader(
            t("step4_uploader_yaml_label_step4"),
            type=["yaml", "yml"],
            key="yaml_uploader_step4_i18n",
        )  # Nueva key para evitar conflictos

        # Definir una ruta fija en el servidor para el archivo YAML que usará Archy
        # os.getcwd() será /app dentro del contenedor Docker
        server_side_yaml_path_for_archy = os.path.join(
            os.getcwd(), "flow_for_archy_update.yaml"
        )

        if yaml_uploaded:
            with open(server_side_yaml_path_for_archy, "wb") as f:
                f.write(yaml_uploaded.read())
            st.success(t("step4_success_yaml_loaded_step4"))

        st.markdown(t("step4_markdown_genesys_creds"))
        client_id = st.text_input(t("step4_input_client_id"))
        client_secret = st.text_input(t("step4_input_client_secret"), type="password")
        location = st.selectbox(
            t("step4_select_location"),
            [
                "mypurecloud.com",
                "apne2.pure.cloud",
                "apne3.pure.cloud",
                "aps1.pure.cloud",
                "cac1.pure.cloud",
                "euc2.pure.cloud",
                "euw2.pure.cloud",
                "mec1.pure.cloud",
                "mypurecloud.com.au",
                "mypurecloud.de",
                "mypurecloud.ie",
                "mypurecloud.jp",
                "sae1.pure.cloud",
                "use2.us-gov-pure.cloud",
                "usw2.pure.cloud",
            ],
        )

        if st.button(t("step4_button_publish")):
            # Verificar si el archivo YAML fue cargado y guardado en el servidor
            yaml_file_for_archy_exists = yaml_uploaded is not None and os.path.exists(
                server_side_yaml_path_for_archy
            )

            if not all(
                [yaml_file_for_archy_exists, client_id, client_secret, location]
            ):
                st.error(t("step4_error_missing_data"))
                if not yaml_file_for_archy_exists:
                    st.warning(
                        t("step4_warning_no_yaml_uploaded_for_publish")
                    )  # Nueva clave de traducción
            else:
                try:
                    import subprocess

                    comando = [
                        "/usr/local/bin/archy",
                        "update",
                        "--file",
                        server_side_yaml_path_for_archy,  # Usar la ruta del archivo en el servidor
                        "--clientId",
                        client_id,
                        "--clientSecret",
                        client_secret,
                        "--location",
                        location,
                    ]

                    st.markdown(
                        t("step4_markdown_executing_command", command=" ".join(comando))
                    )

                    result = subprocess.run(
                        comando,
                        capture_output=True,
                        text=True,
                    )

                    st.markdown(f"#### {t('step4_markdown_stdout')}")
                    st.code(
                        result.stdout or t("step4_text_empty_output"), language="bash"
                    )

                    st.markdown(f"#### {t('step4_markdown_stderr')}")
                    st.code(
                        result.stderr or t("step4_text_empty_output"), language="bash"
                    )

                    if result.returncode == 0:
                        st.success(t("step4_success_publish"))
                    else:
                        st.error(t("step4_error_publish"))
                        # Intentar mostrar logs de Archy
                        try:
                            log_dir = "/opt/archy/debug"
                            if os.path.exists(log_dir):
                                logs = sorted(
                                    [
                                        f
                                        for f in os.listdir(log_dir)
                                        if f.endswith(".txt")
                                    ]
                                )
                                latest_log = logs[-1] if logs else None

                                if latest_log:
                                    st.markdown(f"#### {t('step4_markdown_archy_log')}")
                                    with open(
                                        os.path.join(log_dir, latest_log), "r"
                                    ) as f:
                                        log_contents = f.read()

                                    st.download_button(
                                        label=t(
                                            "step4_download_log_label",
                                            log_file=latest_log,
                                        ),
                                        data=log_contents,
                                        file_name=latest_log,
                                        mime="text/plain",
                                    )
                            elif (
                                result.returncode != 0
                            ):  # Solo mostrar si hubo un error en Archy y el dir no existe
                                st.info(
                                    t("step4_info_log_dir_not_found", log_dir=log_dir)
                                )
                        except Exception as log_ex:
                            st.warning(
                                t(
                                    "step4_warning_log_processing_error",
                                    error=str(log_ex),
                                )
                            )

                except FileNotFoundError:  # Específico para el ejecutable de Archy
                    st.error(t("step4_error_archy_not_found_executable"))
                except Exception as e:
                    st.error(t("step4_error_archy_execution"))
                    st.exception(e)


if __name__ == "__main__":
    main()
