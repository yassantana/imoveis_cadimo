import requests
import time
import csv
import pyodbc
import os
import shutil
from datetime import datetime  

LOGIN_URL = "https://api.devolusvistoria.com.br/auth/login/"
IMOVEIS_URL = "https://api.devolusvistoria.com.br/imoveis/?ativo=true&pagina={}"
EMAIL = ""
SENHA = ""
ARQUIVO_CSV = "imoveis_completos.csv"
PAUSA_REQUISICOES = 1  

SERVER = ""
DATABASE = ""
USERNAME = ""
PASSWORD = ""
TABELA = "TB_API_TORRES_MELO_DEVOLUS"
BATCH_SIZE = 500

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def autenticar():
    body = {"email": EMAIL, "senha": SENHA}
    headers = {"Content-Type": "application/json"}
    response = requests.post(LOGIN_URL, json=body, headers=headers)

    if response.status_code != 200:
        log(f"❌ Erro ao autenticar: {response.status_code} - {response.text}")
        return None

    token = response.text.strip()
    token_bearer = f"Bearer {token}"
    log(f"🔑 Novo token gerado com sucesso! (prefixo: {token[:15]}...)")
    return token_bearer

def listar_imoveis(pagina, token):
    url = IMOVEIS_URL.format(pagina)
    headers = {"Authorization": token}
    response = requests.get(url, headers=headers)

    if response.status_code in [401, 403]:
        log(f"⚠ Erro {response.status_code}: Token inválido/expirado.")
        return "REAUTH"
    elif response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        log(f"⚠ Erro 429: limite atingido. Aguardando {retry_after} segundos...")
        time.sleep(retry_after)
        return "RETRY"
    elif response.status_code != 200:
        log(f"❌ Erro {response.status_code} na página {pagina}: {response.text}")
        return None

    try:
        return response.json()
    except Exception as e:
        log(f"❌ Não foi possível decodificar JSON: {response.text}")
        return None

def salvar_csv(imoveis):
    colunas = ["codigoExterno", "endereco", "numero", "complemento", "bairro",
               "cidade", "uf", "cep", "tipoImovel", "metragem", "status"]

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"imoveis_completos_{timestamp}.csv"

    caminho_principal = os.path.join(r"C:\Users\yasmin\Desktop\devolus_csv", nome_arquivo)

    with open(caminho_principal, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(imoveis)

    pasta_copia = r"C:\Users\yasmin\Desktop\torres_codigos"
    os.makedirs(pasta_copia, exist_ok=True)

    caminho_copia = os.path.join(pasta_copia, nome_arquivo)

    shutil.copy2(caminho_principal, caminho_copia)

    log(f"💾 CSV salvo em: {caminho_principal}")
    log(f"📂 Cópia criada em: {caminho_copia}")

def salvar_sql(imoveis):
    try:
        conn = pyodbc.connect(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={USERNAME};"
            f"PWD={PASSWORD};"
            "TrustServerCertificate=yes;"
        )
        cursor = conn.cursor()

        for imovel in imoveis:
            cursor.execute(f"""
                INSERT INTO {TABELA} 
                (BAIRRO, CEP, ENDERECO, ATIVO, COMPLEMENTO, NUMERO, ID, METRAGEM, CODIGO_MOBILE, UF, TIPO_IMOVEL, CODIGO_EXTERNO, CIDADE, DATA_REGARGA)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                imovel.get("bairro"),
                imovel.get("cep"),
                imovel.get("endereco"),
                1,  
                imovel.get("complemento"),
                imovel.get("numero"),
                imovel.get("id"),
                imovel.get("metragem"),
                imovel.get("codigoMobile"),
                imovel.get("uf"),
                imovel.get("tipoImovel"),
                imovel.get("codigoExterno"),
                imovel.get("cidade"),
                datetime.now()  
            ))

        conn.commit()
        cursor.close()
        conn.close()
        log(f"💾 {len(imoveis)} imóveis inseridos no banco {DATABASE}.{TABELA}")

    except Exception as e:
        log(f"❌ Erro ao salvar no SQL Server: {e}")


def main():
    token = autenticar()
    if not token:
        return

    todos_imoveis = []
    pagina = 1
    contador_requisicoes = 0

    log("🔄 Iniciando captura de imóveis da API...")

    while True:
        imoveis = listar_imoveis(pagina, token)

        if imoveis == "REAUTH":
            token = autenticar()
            if not token:
                break
            continue

        if imoveis == "RETRY":
            continue

        if not imoveis:
            log("✅ Nenhum imóvel encontrado, fim da coleta.")
            break

        lista_atual = []
        for imovel in imoveis:
            if imovel.get("ativo"):
                lista_atual.append({
                    "codigoExterno": imovel.get("codigoExterno"),
                    "endereco": imovel.get("endereco"),
                    "numero": imovel.get("numero"),
                    "complemento": imovel.get("complemento"),
                    "bairro": imovel.get("bairro"),
                    "cidade": imovel.get("cidade"),
                    "uf": imovel.get("uf"),
                    "cep": imovel.get("cep"),
                    "tipoImovel": imovel.get("tipoImovel"),
                    "metragem": imovel.get("metragem"),
                    "status": "Ativo"
                })

        if not lista_atual:
            log(f"✅ Página {pagina} não retornou imóveis ativos.")
        else:
            todos_imoveis.extend(lista_atual)
            log(f"📄 Página {pagina} capturada ({len(lista_atual)} imóveis ativos).")

        pagina += 1
        contador_requisicoes += 1
        time.sleep(PAUSA_REQUISICOES)

    salvar_csv(todos_imoveis)
    salvar_sql(todos_imoveis)  

    log(f"🏁 Finalizado! Total de imóveis salvos: {len(todos_imoveis)}")
    log(f"📊 Total de páginas percorridas: {pagina-1}")
    log(f"📡 Total de requisições feitas: {contador_requisicoes}")

if __name__ == "__main__":
    main()

