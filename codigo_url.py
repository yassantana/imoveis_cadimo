import pandas as pd
import requests
import time

csv_faltantes = r"C:\Users\yasmin\Desktop\torres_codigos\imoveis_faltantes.csv"

CHECK_URL = "https://api.devolusvistoria.com.br/imoveis/qtd/?codigoExterno={}"
EMAIL = ""
SENHA = ""

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def autenticar():
    LOGIN_URL = "https://api.devolusvistoria.com.br/auth/login/"
    body = {"email": EMAIL, "senha": SENHA}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(LOGIN_URL, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
        token = resp.text.strip()
        return f"Bearer {token}"
    except Exception as e:
        log(f"❌ Erro no login: {e}")
        return None

def verificar_codigo(codigo, token):
    url = CHECK_URL.format(codigo)
    headers = {"Authorization": token}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        qtd = resp.json()
        return qtd == 1
    except Exception as e:
        log(f"⚠️ Erro ao verificar código {codigo}: {e}")
        return False

def main():
    log("🚀 Iniciando verificação de faltantes diretamente na API...")

    token = autenticar()
    if not token:
        return

    df = pd.read_csv(csv_faltantes, dtype=str).fillna("")
    log(f"📂 CSV carregado com {len(df)} imóveis faltantes (pré-verificação).")

    codigos_removidos = []
    for idx, row in df.iterrows():
        codigo = row["codigo"]
        if verificar_codigo(codigo, token):
            log(f"✅ Imóvel {codigo} já existe na API → removido do CSV.")
            codigos_removidos.append(idx)
        else:
            log(f"❌ Imóvel {codigo} não encontrado na API → mantido no CSV.")

        time.sleep(0.3) 

    df.drop(index=codigos_removidos, inplace=True)
    df.to_csv(csv_faltantes, index=False, encoding="utf-8-sig")

    log(f"📂 CSV atualizado com {len(df)} imóveis realmente faltando: {csv_faltantes}")
    if codigos_removidos:
        log(f"ℹ️ {len(codigos_removidos)} imóveis foram removidos do CSV por já existirem na API.")

    log("✅ Processo concluído.")

if __name__ == "__main__":
    main()
