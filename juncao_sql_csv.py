import requests
import ssl
import os
import time
import json
import csv
import pyodbc
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

TOKEN_FIXO = ""
CPF_CNPJ_EMPRESA = ""

PASTA = r"C:\Users\yasmin\Desktop\cadimo_csv"
PASTA_COPIA = r"C:\Users\yasmin\Desktop\torres_codigos"
LIMIT = 50

URL_TOKEN = "https://cadimo.imobsoft.com.br:8053/ValidaParceiro"
URL_IMOVEIS = "https://cadimo.imobsoft.com.br:8053/CarregaImoveis"

SERVER = ""
DATABASE = "DWHeaders"
USERNAME = ""
PASSWORD = ""
TABELA = ""
BATCH_SIZE = 500  

os.makedirs(PASTA, exist_ok=True)
os.makedirs(PASTA_COPIA, exist_ok=True)

class TLS12Adapter(HTTPAdapter):
    def __init__(self, ciphers=None, *args, **kwargs):
        self.ciphers = ciphers
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = ssl.create_default_context()
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            pass
        if self.ciphers:
            ctx.set_ciphers(self.ciphers)
        pool_kwargs['ssl_context'] = ctx
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

def get_temp_token(session):
    headers = {"token-conta": TOKEN_FIXO}
    r = session.get(URL_TOKEN, headers=headers, timeout=30, verify=True)
    r.raise_for_status()
    return r.text.strip()

def limpar_json(texto):
    return ''.join(c if c >= " " or c in "\r\n\t" else ' ' for c in texto)

def baixar_paginas(session, token_temp):
    offset = 0
    pagina = 0
    total_api = None
    todos_imoveis = []

    while True:
        headers = {
            "Authorization": f"Bearer {token_temp}",
            "cpf_cnpj_empresa": CPF_CNPJ_EMPRESA,
            "limit": str(LIMIT),
            "token-conta": TOKEN_FIXO,
            "offset": str(offset)
        }
        r = session.get(URL_IMOVEIS, headers=headers, timeout=60, verify=True)
        r.raise_for_status()

        try:
            data = r.json()
        except Exception:
            data = json.loads(limpar_json(r.text))

        if total_api is None:
            total_api = data.get("total", None)

        imoveis = data.get("imoveis", [])
        if not imoveis:
            break

        todos_imoveis.extend(imoveis)
        print(f"[OK] Página {pagina} processada -> {len(imoveis)} imóveis (offset {offset})")

        offset += LIMIT
        pagina += 1
        if total_api is not None and offset >= total_api:
            break

        time.sleep(0.2)

    return total_api, todos_imoveis

def tratar_valor(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s if s != "" else None

def tratar_data(valor):
    v = tratar_valor(valor)
    if v is None:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%Y-%m-%d")
    except:
        pass
    try:
        return datetime.strptime(v, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        pass
    try:
        return datetime.strptime(v, "%d/%m/%Y %H:%M").strftime("%Y-%m-%d")
    except:
        pass
    try:
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=float(v))).strftime("%Y-%m-%d")
    except:
        return None

def tratar_data_hora(valor):
    v = tratar_valor(valor)
    if v is None:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass
    try:
        dt = datetime.strptime(v, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d 00:00:00")
    except:
        pass
    try:
        return datetime.strptime(v, "%d/%m/%Y %H:%M").strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass
    try:
        dt = datetime.strptime(v, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d 00:00:00")
    except:
        return None

def tratar_numero(valor):
    """Converte valor para float (usado para área e para leitura do CSV)"""
    v = tratar_valor(valor)
    if v is None:
        return None
    try:
        v = str(v).replace(".", "").replace(",", ".")
        return float(v)
    except ValueError:
        return None

def formatar_valor_brasileiro(valor):
    """Formata número no padrão brasileiro ex: 2668.75 -> '2.668,75' """
    num = tratar_numero(valor)
    if num is None:
        return None
    # arredonda 2 casas e formata milhar com ponto e decimal com vírgula
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def tratar_inteiro(valor):
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))
    except:
        return None

def padronizar_contrato(valor):
    if not valor:
        return None
    return str(valor).strip().upper()

def salvar_csv(todos_imoveis):
    campos = [
        "codigo", "tipo", "situacao", "area", "finalidade", "contrato_loc", "inicio_ctr_loc", "fim_ctr_loc", "valor", "valor_condominio", "valor_iptu", 
        "nome_condominio", "dia_vencimento_condominio", "condominio_controlado_pela_adm", "condominio_pago_pela_adm", "tipo_fianca",
        "endereco", "complemento", "numero", "bairro", "cidade", "uf", "cep",
        "captador", "ctr_Adm", "ctr_Adm_inicio", "txAdm", "Tx_Adm_Extra", "Num_parcela_com_Extra",
        "nome_proprietario", "cpf_cnpj_proprietario", "percentual_proprietario", "email",
        "nome_proprietario2", "cpf_cnpj_proprietario2", "percentual_proprietario2", "email_2",
        "data_recarga"
    ]

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    caminho_csv = os.path.join(PASTA, f"torres_{timestamp}.csv")
    caminho_copia = os.path.join(PASTA_COPIA, f"torres_copia_{timestamp}.csv")

    todas_linhas = []

    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for imovel in todos_imoveis:
            linha = {key: None for key in campos}
            linha.update({
                "codigo": imovel.get("codigo"),
                "tipo": imovel.get("tipo"),
                "situacao": imovel.get("situacao"),
                "area": imovel.get("area"),
                "finalidade": imovel.get("finalidade"),
                "contrato_loc": imovel.get("contrato_loc"),
                "inicio_ctr_loc": imovel.get("inicio_ctr_loc"),
                "fim_ctr_loc": imovel.get("fim_ctr_loc"),
                "valor": formatar_valor_brasileiro(imovel.get("valor")),
                "valor_condominio": formatar_valor_brasileiro(imovel.get("valor_condominio")),
                "valor_iptu": formatar_valor_brasileiro(imovel.get("valor_iptu")),
                "nome_condominio": imovel.get("nome_condominio"),
                "dia_vencimento_condominio": imovel.get("dia_vencimento_condominio"),
                "condominio_controlado_pela_adm": imovel.get("condominio_controlado_pela_adm"),
                "condominio_pago_pela_adm": imovel.get("condominio_pago_pela_adm"),
                "tipo_fianca": imovel.get("tipo_fianca"),
                "endereco": imovel.get("logradouro"),
                "complemento": imovel.get("complemento"),
                "numero": imovel.get("numero"),
                "bairro": imovel.get("bairro"),
                "cidade": imovel.get("cidade"),
                "uf": imovel.get("uf"),
                "cep": imovel.get("cep"),
                "captador": imovel.get("captador"),
                "ctr_Adm": imovel.get("ctr_Adm"),
                "ctr_Adm_inicio": imovel.get("ctr_Adm_inicio"),
                "txAdm": imovel.get("txAdm"),
                "Tx_Adm_Extra": imovel.get("Tx_Adm_Extra"),
                "Num_parcela_com_Extra": imovel.get("Num_parcela_com_Extra"),
                "data_recarga": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            proprietarios = imovel.get("proprietarios", [])
            if len(proprietarios) > 0:
                linha["nome_proprietario"] = proprietarios[0].get("nome")
                linha["cpf_cnpj_proprietario"] = proprietarios[0].get("cpf_cnpj")
                linha["percentual_proprietario"] = proprietarios[0].get("percentual")
                linha["email"] = proprietarios[0].get("email")
            if len(proprietarios) > 1:
                linha["nome_proprietario2"] = proprietarios[1].get("nome")
                linha["cpf_cnpj_proprietario2"] = proprietarios[1].get("cpf_cnpj")
                linha["percentual_proprietario2"] = proprietarios[1].get("percentual")
                linha["email_2"] = proprietarios[1].get("email")

            writer.writerow(linha)
            todas_linhas.append(linha)

    with open(caminho_copia, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for linha in todas_linhas:
            writer.writerow(linha)

    print(f"[SALVO CSV FINAL] {caminho_csv}")
    print(f"[SALVO CÓPIA CSV] {caminho_copia}")
    return caminho_csv

def inserir_csv_sql(caminho_csv):
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD}"
    )
    cursor = conn.cursor()

    with open(caminho_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        dados_para_insert = []
        for row in reader:
            dados_para_insert.append((
                tratar_valor(row.get("codigo")),
                (str(row.get("tipo") or "").strip().upper()),
                tratar_valor(row.get("situacao")),
                tratar_numero(row.get("area")),
                tratar_valor(row.get("finalidade")),
                padronizar_contrato(row.get("contrato_loc")),
                tratar_data(row.get("inicio_ctr_loc")),
                tratar_data(row.get("fim_ctr_loc")),
                round(tratar_numero(row.get("valor")), 2) if tratar_numero(row.get("valor")) is not None else None,
                round(float(str(row.get("valor_condominio")).replace('.', '').replace(',', '.')), 2) if row.get("valor_condominio") not in (None, '', 'NULL') else None,
                round(float(str(row.get("valor_iptu")).replace('.', '').replace(',', '.')), 2) if row.get("valor_iptu") not in (None, '', 'NULL') else None,
                tratar_valor(row.get("nome_condominio")),
                tratar_inteiro(row.get("dia_vencimento_condominio")),
                str(row.get("condominio_controlado_pela_adm")).lower() if row.get("condominio_controlado_pela_adm") is not None else None,
                str(row.get("condominio_pago_pela_adm")).lower() if row.get("condominio_pago_pela_adm") is not None else None,
                tratar_valor(row.get("tipo_fianca")),
                tratar_valor(row.get("endereco")),
                tratar_valor(row.get("complemento")),
                tratar_valor(row.get("numero")),
                tratar_valor(row.get("bairro")),
                tratar_valor(row.get("cidade")),
                tratar_valor(row.get("uf")),
                tratar_valor(row.get("cep")),
                tratar_valor(row.get("captador")),
                padronizar_contrato(row.get("ctr_Adm")),
                tratar_data(row.get("ctr_Adm_inicio")),
                tratar_inteiro(row.get("txAdm")),
                tratar_inteiro(row.get("Tx_Adm_Extra")),
                tratar_inteiro(row.get("Num_parcela_com_Extra")),
                tratar_valor(row.get("nome_proprietario")),
                tratar_valor(row.get("cpf_cnpj_proprietario")),
                tratar_inteiro(row.get("percentual_proprietario")),
                tratar_valor(row.get("email")),
                tratar_valor(row.get("nome_proprietario2")),
                tratar_valor(row.get("cpf_cnpj_proprietario2")),
                tratar_inteiro(row.get("percentual_proprietario2")),
                tratar_valor(row.get("email_2")),
                tratar_data_hora(row.get("data_recarga"))
            ))

    cursor.fast_executemany = True
    cursor.executemany(f"""
        INSERT INTO {TABELA} (
            [CODIGO],[TIPO],[SITUACAO],[AREA],[FINALIDADE],
            [CONTRATO_LOC],[INICIO_CTR_LOC],[FIM_CTR_LOC],
            [VALOR],[VALOR_CONDOMINIO],[VALOR_IPTU],
            [NOME_CONDOMINIO],[DIA_VENCIMENTO_CONDOMINIO],[CONDOMINIO_CONTROLADO_PELA_ADM],[CONDOMINIO_PAGO_PELA_ADM],
            [TIPO_FIANCA],[LOGRADOURO],[COMPLEMENTO],[NUMERO],
            [BAIRRO],[CIDADE],[UF],[CEP],[CAPTADOR],
            [CTR_ADM],[CTR_ADM_INICIO],
            [TXADM],[TX_ADM_EXTRA],[NUM_PARCELA_COM_EXTRA],
            [NOME_PROPRIETARIO1],[CPF_CNPJ_PROPRIETARIO1],[PERCENTUAL_PROPRIETARIO1],[EMAIL_PROPRIETARIO1],
            [NOME_PROPRIETARIO2],[CPF_CNPJ_PROPRIETARIO2],[PERCENTUAL_PROPRIETARIO2],[EMAIL_PROPRIETARIO2],
            [DATA_RECARGA]
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, dados_para_insert)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Dados inseridos com sucesso no SQL Server!")

if __name__ == "__main__":
    session = requests.Session()
    session.mount("https://", TLS12Adapter("DEFAULT:@SECLEVEL=1"))

    print("🔑 Obtendo token temporário...")
    token_temp = get_temp_token(session)
    print("✅ Token obtido com sucesso.")

    total_api, todos_imoveis = baixar_paginas(session, token_temp)
    print(f"\n📊 Total de imóveis baixados: {len(todos_imoveis)} (API informou: {total_api})")

    caminho_csv = salvar_csv(todos_imoveis)
    inserir_csv_sql(caminho_csv)
