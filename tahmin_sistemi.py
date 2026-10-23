import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import urllib3
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("==========================================================")
print(f"RAPOR GÜNCELLEME ZAMANI: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("==========================================================")

API_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")
HEADERS = {"X-Auth-Token": API_TOKEN}
BASE_URL = "https://football-data.org"

def guncel_verileri_cek():
    print("Football-Data.org API'sinden güncel maçlar çekiliyor...")
    try:
        tarih_beri = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"{BASE_URL}/matches?dateFrom={tarih_beri}&dateTo={datetime.now().strftime('%Y-%m-%d')}"
        response = requests.get(url, headers=HEADERS, verify=False)
        if response.status_code == 200:
            print("Son haftanın maç verileri başarıyla çekildi.")
            return response.json()
        return None
    except Exception as e:
        print(f"API Bağlantı es geçildi (SSL/Kota): {e}")
        return None

def yapay_zeka_ve_oruntu_motoru(df):
    df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'])
    
    df['tarih'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
    df['takim'] = df['HomeTeam'].astype(str).str.strip()
    df['rakip'] = df['AwayTeam'].astype(str).str.strip()
    df['ev_gol'] = df['FTHG'].astype(int)
    df['dep_gol'] = df['FTAG'].astype(int)
    
    df['kirmizi_kart_sayisi'] = df['HR'].fillna(0).astype(int) + df['AR'].fillna(0).astype(int)
    df['toplam_gol'] = df['ev_gol'] + df['dep_gol']
    
    uyn_12_21 = []
    uyn_7plus = []
    uyn_33 = []
    uyn_ozel_kirmizi = []
    
    df = df.sort_values(by='tarih')
    
    for idx, row in df.iterrows():
        if 'HTHG' in df.columns and 'HTAG' in df.columns:
            try:
                iy_ev = int(row['HTHG'])
                iy_dep = int(row['HTAG'])
                ms_ev = row['ev_gol']
                ms_dep = row['dep_gol']
                if (iy_ev > iy_dep and ms_ev < ms_dep) or (iy_ev < iy_dep and ms_ev > ms_dep):
                    uyn_12_21.append(f"{row['Date']} | {row['takim']} - {row['rakip']} ({iy_ev}-{iy_dep} / {ms_ev}-{ms_dep})")
            except:
                pass
                
        if row['toplam_gol'] >= 7:
            uyn_7plus.append(f"{row['Date']} | {row['takim']} {row['ev_gol']}-{row['dep_gol']} {row['rakip']}")
            
        if row['ev_gol'] == 3 and row['dep_gol'] == 3:
            uyn_33.append(f"{row['Date']} | {row['takim']} vs {row['rakip']}")
            
    tum_takimlar = set(df['takim'].unique()).union(set(df['rakip'].unique()))
    for takim in tum_takimlar:
        takim_maclari = df[(df['takim'] == takim) | (df['rakip'] == takim)].tail(2)
        if len(takim_maclari) == 2:
            uygun_mac_sayisi = 0
            for _, mac in takim_maclari.iterrows():
                g_ev, g_dep = mac['ev_gol'], mac['dep_gol']
                gecerli_skor = (g_ev == 1 and g_dep == 1) or \
                               (g_ev == 1 and g_dep == 0) or \
                               (g_ev == 0 and g_dep == 1) or \
                               (g_ev == 2 and g_dep == 0) or \
                               (g_ev == 0 and g_dep == 2)
                kirmizi_var_mi = mac['kirmizi_kart_sayisi'] > 0
                if gecerli_skor and kirmizi_var_mi:
                    uygun_mac_sayisi += 1
            if uygun_mac_sayisi == 2:
                uyn_ozel_kirmizi.append(takim)

    df['mac_sonucu'] = np.where(df['ev_gol'] > df['dep_gol'], '1', 
                        np.where(df['ev_gol'] == df['dep_gol'], 'X', '2'))
    
    df['is_33'] = np.where((df['ev_gol'] == 3) & (df['dep_gol'] == 3), 1, 0)
    df['is_7plus'] = np.where(df['toplam_gol'] >= 7, 1, 0)
    df['kirmizi_kart_var_mi'] = np.where(df['kirmizi_kart_sayisi'] > 0, 1, 0)
    
    le_takim = LabelEncoder()
    df['takim_kod'] = le_takim.fit_transform(df['takim'])
    df['rakip_kod'] = le_takim.fit_transform(df['rakip'])
    
    X = df[['takim_kod', 'rakip_kod', 'is_33', 'is_7plus', 'kirmizi_kart_var_mi']]
    y = df['mac_sonucu']
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    print("\n=== CUMA ÖĞLEN TAHMİN VE ÖRÜNTÜ RAPORU ===")
    print(f"\n 1/2 veya 2/1 Biten Ters Maçlar ({len(uyn_12_21)} adet):")
    for m in uyn_12_21[:10]: print(f" -> {m}")
    
    print(f"\n 7+ Gol Biten Maçlar ({len(uyn_7plus)} adet):")
    for m in uyn_7plus[:10]: print(f" -> {m}")
    
    print(f"\n 3-3 Biten Maçlar ({len(uyn_33)} adet):")
    for m in uyn_33[:10]: print(f" -> {m}")
    
    print(f"\n Son 2 Maçında Kırmızı Kartlı Seri Yakalayan Takımlar:")
    print(f" -> {list(set(uyn_ozel_kirmizi)) if uyn_ozel_kirmizi else 'Bulunamadı.'}")
    
    print("\n YAPAY ZEKA GELECEK MAÇ MODEL TESTİ")
    try:
        ornek_mac = pd.DataFrame([{'takim_kod': df['takim_kod'].iloc[-1], 'rakip_kod': df['rakip_kod'].iloc[-1], 'is_33': 0, 'is_7plus': 0, 'kirmizi_kart_var_mi': 1}])
        probs = model.predict_proba(ornek_mac)
        classes = model.classes_
        print(f"Maç Simülasyonu: {df['takim'].iloc[-1]} vs {df['rakip'].iloc[-1]}")
        for c, p in zip(classes, probs):
            print(f" -> Sonuç {c} Olma Olasılığı: %{p*100:.2f}")
    except Exception as e:
        print(f"Tahmin simülasyon hatası: {e}")
    print("==========================================\n")

if __name__ == "__main__":
    dosyalar = ["sezon22_23.csv", "sezon23_24.csv", "sezon24_25.csv"]
    mevcut_dosyalar = [f for f in dosyalar if os.path.exists(f)]
    
    if mevcut_dosyalar:
        print(f"Algılanan sezon dosyaları otomatik birleştiriliyor: {mevcut_dosyalar}")
        # Tüm dosyaları oku ve alt alta yapıştır
        bilesik_df = pd.concat([pd.read_csv(f) for f in mevcut_dosyalar], ignore_index=True)
        guncel_verileri_cek()
        yapay_zeka_ve_oruntu_motoru(bilesik_df)
    else:
        print("Lütfen depoya en az bir adet sezon dosyası (Örn: 'sezon24_25.csv') yükleyin.")
