import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="XAU/USD Ons Altın Dinamik SAR Haritası & Strateji Motoru", 
    layout="wide"
)

st.title(" ONS ALTIN (XAU/USD) DİNAMİK SAR HARİTASI VE STRATEJİ MOTORU")
st.markdown("*(Emrah Uludağ Ons Piyasası SAR Analiz Metodolojisi)*")

# ---------------------------------------------------------
# YFINANCE İLE VERİ ÇEKME VE SAR HESAPLAMA
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_gold_data():
    """yfinance ile altın verilerini çek ve SAR hesapla"""
    try:
        # Altın futures verisi (GC=F)
        gold = yf.Ticker("GC=F")
        
        # Farklı zaman dilimleri için veri çek
        timeframes = {
            "1D": {"period": "1y", "interval": "1d", "name": "Günlük"},
            "1W": {"period": "5y", "interval": "1wk", "name": "Haftalık"},
            "1M": {"period": "10y", "interval": "1mo", "name": "Aylık"}
        }
        
        results = {}
        current_price = 0
        
        for tf, config in timeframes.items():
            try:
                df = gold.history(period=config["period"], interval=config["interval"])
                
                if len(df) > 0:
                    current_price = df['Close'].iloc[-1]
                    
                    # Parabolic SAR hesapla (basit versiyon)
                    high = df['High']
                    low = df['Low']
                    close = df['Close']
                    
                    # SAR hesaplaması
                    sar = calculate_sar(high, low, close)
                    
                    if len(sar) > 0:
                        last_sar = sar.iloc[-1]
                        sar_type = "Direnç" if last_sar > current_price else "Destek"
                        
                        results[tf] = {
                            "label": config["name"],
                            "sar": last_sar,
                            "type": sar_type,
                            "price": current_price
                        }
            except Exception as e:
                st.warning(f"{tf} için veri alınamadı: {e}")
                continue
        
        return current_price, results
        
    except Exception as e:
        st.error(f"Genel hata: {e}")
        return 0, {}

def calculate_sar(high, low, close, af=0.02, max_af=0.2):
    """Basit Parabolic SAR hesaplama"""
    sar = pd.Series(index=close.index, dtype=float)
    uptrend = True
    ep = high.iloc[0]
    af_current = af
    sar.iloc[0] = low.iloc[0]
    
    for i in range(1, len(close)):
        if uptrend:
            sar.iloc[i] = sar.iloc[i-1] + af_current * (ep - sar.iloc[i-1])
            if low.iloc[i] < sar.iloc[i]:
                uptrend = False
                sar.iloc[i] = ep
                ep = low.iloc[i]
                af_current = af
            else:
                if high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af_current = min(af_current + af, max_af)
        else:
            sar.iloc[i] = sar.iloc[i-1] + af_current * (ep - sar.iloc[i-1])
            if high.iloc[i] > sar.iloc[i]:
                uptrend = True
                sar.iloc[i] = ep
                ep = high.iloc[i]
                af_current = af
            else:
                if low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af_current = min(af_current + af, max_af)
    
    return sar

# ---------------------------------------------------------
# ANALİZ MOTORU
# ---------------------------------------------------------
def analyze_sar(price, sar_data):
    """Uludağ metodolojisine göre analiz"""
    analysis = {
        "price": price,
        "sars_above": {},
        "sars_below": {},
        "recommendation": "",
        "reasoning": []
    }
    
    for tf, data in sar_data.items():
        if data["type"] == "Direnç":
            analysis["sars_above"][tf] = data["sar"]
        else:
            analysis["sars_below"][tf] = data["sar"]
    
    if len(analysis["sars_above"]) == 0:
        analysis["recommendation"] = "SERİ HAREKET - ALIM YAP"
        analysis["reasoning"] = ["✓ Üstte SAR yok", "✓ Tüm dirençler temizlenmiş"]
    elif len(analysis["sars_above"]) >= 3:
        analysis["recommendation"] = "GÜÇLÜ DİRENÇ - BEKLE"
        analysis["reasoning"] = [f" Üstte {len(analysis['sars_above'])} SAR var", "✗ Yükseliş zor"]
    else:
        analysis["recommendation"] = "TEPKİ YÜKSELİŞİ"
        analysis["reasoning"] = [f"⚠️ {len(analysis['sars_above'])} direnç var", "→ Kademeli takip"]
    
    return analysis

# ---------------------------------------------------------
# ANA UYGULAMA
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🔥 CANLI ANALİZ", "📖 METODOLOJİ"])

with tab1:
    st.subheader("⚙️ Veriler Yükleniyor...")
    
    with st.spinner("Altın verileri çekiliyor..."):
        price, sar_data = fetch_gold_data()
    
    if price > 0:
        st.success(f"✅ Veri alındı! Fiyat: ${price:.2f}")
        
        # SAR Kartları
        st.subheader("📊 SAR SEVİYELERİ")
        cols = st.columns(len(sar_data))
        
        for idx, (tf, data) in enumerate(sar_data.items()):
            with cols[idx]:
                if data["type"] == "Destek":
                    st.success(f"**{data['label']}**\n\n${data['sar']:.2f}\n\n🟢 DESTEK")
                else:
                    st.error(f"**{data['label']}**\n\n${data['sar']:.2f}\n\n🔴 DİRENÇ")
        
        st.divider()
        
        # Analiz
        analysis = analyze_sar(price, sar_data)
        
        st.subheader("💡 ANALİZ SONUCU")
        
        if "SERİ HAREKET" in analysis["recommendation"]:
            st.success(f"###  {analysis['recommendation']}")
        elif "DİRENÇ" in analysis["recommendation"]:
            st.error(f"### 🔴 {analysis['recommendation']}")
        else:
            st.warning(f"### 🟡 {analysis['recommendation']}")
        
        for reason in analysis["reasoning"]:
            st.markdown(reason)
        
        # Tablo
        st.subheader(" DETAYLI TABLO")
        df = pd.DataFrame([
            {
                "Zaman Dilimi": data["label"],
                "SAR": f"${data['sar']:.2f}",
                "Konum": data["type"],
                "Fark": f"${price - data['sar']:+.2f}"
            }
            for data in sar_data.values()
        ])
        st.dataframe(df, use_container_width=True)
        
    else:
        st.error("❌ Veri çekilemedi. Lütfen daha sonra tekrar deneyin.")

with tab2:
    st.header("📖 METODOLOJİ")
    st.markdown("""
    ## Uludağ SAR Metodolojisi
    
    ### Temel Kurallar:
    1. **Üstünde SAR Bırakmama:** Üstte SAR yoksa seri hareket
    2. **Zaman Dilimi Hiyerarşisi:** Aylık → Haftalık → Günlük
    3. **Dinamik Stop-Loss:** En yakın SAR destek seviyesi
    
    ### Yorumlar:
    - **0 SAR üstte:** 🟢 Seri yükseliş
    - **1-2 SAR üstte:** 🟡 Tepki yükselişi
    - **3+ SAR üstte:**  Güçlü direnç, bekle
    """)

st.divider()
st.markdown("*Yatırım tavsiyesi değildir.*")
