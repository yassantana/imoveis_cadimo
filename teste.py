import pandas as pd
import requests
import os

pasta = r"C:\Users\yasmin\Desktop\torres_codigos"

def pegar_csv_mais_recente(prefixo):
    arquivos = [f for f in os.listdir(pasta) if f.startswith(prefixo) and f.endswith(".csv")]
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo CSV encontrado para prefixo '{prefixo}'")
   
    caminho_mais_recente = max([os.path.join(pasta, f) for f in arquivos], key=os.path.getmtime)
    return caminho_mais_recente

cadimo_file = pegar_csv_mais_recente("torres")
devolus_file = pegar_csv_mais_recente("imoveis_completos")
saida_faltantes = os.path.join(pasta, "imoveis_faltantes.csv")

cadimo = pd.read_csv(cadimo_file, dtype=str).fillna("")
devolus = pd.read_csv(devolus_file, dtype=str).fillna("")

devolus_ativos = devolus[devolus["status"].str.upper() == "ATIVO"]
imoveis_faltantes = cadimo[~cadimo["codigo"].isin(devolus_ativos["codigoExterno"])]
imoveis_faltantes = imoveis_faltantes[imoveis_faltantes["codigo"].str.len() >= 4]

imoveis_faltantes.to_csv(saida_faltantes, index=False, encoding="utf-8-sig")
print(f"📂 CSV gerado com {len(imoveis_faltantes)} imóveis faltantes: {saida_faltantes}")

sucesso, falha = [], []

API_URL = "https://api.devolusvistoria.com.br/api/imoveis"
TOKEN = "3f57dca4-c52d-44c3-af71-0b932be8a4d3"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

for _, row in imoveis_faltantes.iterrows():
     metragem = 0
     if row.get("area"):
        try:
            area_str = row["area"].replace(".", "").replace(",", ".")
            metragem = float(area_str)
            if metragem.is_integer():
                metragem = int(metragem)
        except:
            metragem = 0

     payload = {
        "codigoExterno": row["codigo"],
        "endereco": row["endereco"],
        "numero": row["numero"],
        "complemento": row["complemento"],
        "bairro": row["bairro"],
        "cidade": row["cidade"],
        "uf": row["uf"],
        "tipoImovel": row["finalidade"],
        "metragem": metragem,
        "cep": row["cep"],
        "ativo": True  
    }

     try:
        resp = requests.post(API_URL, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            print(f"✅ Imóvel {row['codigo']} inserido/atualizado com sucesso. (metragem={metragem})")
            sucesso.append(row["codigo"])
        else:
            print(f"❌ Erro ao inserir {row['codigo']}: {resp.status_code} - {resp.text}")
            falha.append((row["codigo"], resp.text))
     except Exception as e:
        print(f"⚠️ Erro inesperado ao inserir {row['codigo']}: {e}")
        falha.append((row["codigo"], str(e)))

print("\n===== RESUMO =====")
print(f"Imóveis faltantes no teste: {len(imoveis_faltantes)}")
print(f"Inseridos com sucesso: {len(sucesso)}")
print(f"Falharam: {len(falha)}")

if falha:
    print("\nImóveis que falharam:")
    for cod, erro in falha:
        print(f"- {cod}: {erro}")









