import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
import pandas as pd
from datetime import datetime, timedelta

print("==========================================================")
print(f"RAPOR GÜNCELLEME ZAMANI: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("==========================================================")

# 1. API Ayarları ve Veri Çekme
API_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")  # GitHub Secrets'tan güvenli bir şekilde alınacak
HEADERS = {"X-Auth-Token": API_TOKEN}
BASE_URL = "https://football-data.org"

def guncel_verileri_cek():
    print("Football-Data.org API'sinden güncel maçlar çekiliyor...")
    # Türkiye Süper Lig (TSL) lig kodu genellikle 'TR' veya belirli bir ID'dir (Örn: 2011 veya lig araması ile bulunur)
    # Kolaylık ve kota dostu olması açısından sistem son 3 yılın veritabanını (mac_verileri.csv) yerel olarak okur,
    # Cuma sabahları ise sadece son 7 günde oynanan yeni TSL ve Avrupa maçlarını çekip veritabanına ekler.
    
    # NOT: Ücretsiz planda canlı maç limitleri olduğu için mevcut yerel verinizin üzerine 
    # yeni haftanın maçlarını ekleyecek mekanizma aşağıda simüle edilmiştir.
    try:
        # Örnek: Son 7 günün maçlarını çek
        tarih_beri = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"{BASE_URL}/matches?dateFrom={tarih_beri}&dateTo={datetime.now().strftime('%Y-%m-%d')}"
        response = requests.get(url, headers=HEADERS, verify=False)
        if response.status_code == 200:
            print("Son haftanın maç verileri başarıyla çekildi.")
            return response.json()
        else:
            print(f"API Hatası: {response.status_code}")
            return None
    except Exception as e:
        print(f"Bağlantı hatası: {e}")
        return None

# 2. Örüntü Filtreleme Algoritması
def oruntuleri_filtrele(df):
    if df.empty:
        print("Analiz edilecek veri bulunamadı.")
        return
        
    df['toplam_gol'] = df['ev_gol'] + df['dep_gol']
    df['tarih'] = pd.to_datetime(df['tarih'])
    df = df.sort_values(by='tarih')
    
    uyn_12_21 = []
    uyn_7plus = []
    uyn_33 = []
    uyn_ozel_kirmizi = []
    
    # Maç Bazlı Taramalar (1/2, 2/1, 7+, 3-3)
    for idx, row in df.iterrows():
        # 1/2 ve 2/1 kontrolü
        iy_ev, iy_dep = map(int, str(row['iy_skor']).split('-')) if '-' in str(row['iy_skor']) else (0,0)
        ms_ev, ms_dep = row['ev_gol'], row['dep_gol']
        
        if (iy_ev > iy_dep and ms_ev < ms_dep) or (iy_ev < iy_dep and ms_ev > ms_dep):
            uyn_12_21.append(row)
            
        # 7+ Gol Kontrolü
        if row['toplam_gol'] >= 7:
            uyn_7plus.append(row)
            
        # 3-3 Skor Kontrolü
        if ms_ev == 3 and ms_dep == 3:
            uyn_33.append(row)
            
    # Takım Bazlı Son 2 Maç Kontrolü (1-1, 1-0, 2-0 + Kırmızı Kart)
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

    # Sonuçları Rapor Olarak Yazdır
    print("\n=== CUMA ÖĞLEN TAHMİN VE ÖRÜNTÜ RAPORU ===")
    print(f"1/2 veya 2/1 Biten Maç Sayısı: {len(uyn_12_21)}")
    print(f"7+ Gol Biten Maç Sayısı: {len(uyn_7plus)}")
    print(f"3-3 Biten Maç Sayısı: {len(uyn_33)}")
    print(f"Son 2 Maçında Kırmızı Kartlı Seri Yakalayan Takımlar: {list(set(uyn_ozel_kirmizi))}")
    print("==========================================\n")

if __name__ == "__main__":
    # Test veya gerçek çalıştırma için yerel veri setinizi yükleyin
    # Projenizin çalışması için ana dizinde 'mac_verileri.csv' adında bir dosya olmalıdır.
    if os.path.exists("mac_verileri.csv"):
        ana_veri = pd.read_csv("mac_verileri.csv")
        guncel_verileri_cek()  # Haftalık yeni verileri çekmeyi dener
        oruntuleri_filtrele(ana_veri)
    else:
        print("Lütfen ilk etapta son 3 yılın geçmiş verilerini içeren 'mac_verileri.csv' dosyasını yükleyin.")
