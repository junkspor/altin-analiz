import streamlit as st
import streamlit.components.v1 as components
from tradingview_ta import TA_Handler, Interval
from datetime import datetime

# Sayfa Yapılandırması
st.set_page_config(
    page_title="XAU/USD Ons Altın Dinamik SAR Haritası & Strateji Motoru", 
    layout="wide"
)

st.title("📊 ONS ALTIN (XAU/USD) DİNAMİK SAR HARİTASI VE STRATEJİ MOTORU")
st.markdown("*(Emrah Uludağ Ons Piyasası SAR Analiz Metodolojisi)*")

# ---------------------------------------------------------
# HER ZAMAN DİLİMİ İÇİN AYRI AYRI SAR ÇEKME FONKSİYONU
# ---------------------------------------------------------
@st.cache_data(ttl=5)
def fetch_sar_for_timeframe(tf_key):
    """Belirli bir zaman dilimi için SAR verisi çeker"""
    tf_configs = {
        "1H": {"interval": Interval.INTERVAL_1_HOUR, "name": "1 Saatlik"},
        "4H": {"interval": Interval.INTERVAL_4_HOURS, "name": "4 Saatlik"},
        "1D": {"interval": Interval.INTERVAL_1_DAY, "name": "Günlük"},
        "1W": {"interval": Interval.INTERVAL_1_WEEK, "name": "Haftalık"},
        "1M": {"interval": Interval.INTERVAL_1_MONTH, "name": "Aylık"}
    }
    
    if tf_key not in tf_configs:
        return None, None
        
    config = tf_configs[tf_key]
    sources = [
        {"screener": "cfd", "exchange": "OANDA"},
        {"screener": "forex", "exchange": "OANDA"},
        {"screener": "forex", "exchange": "FX_IDC"}
    ]
    
    for src in sources:
        try:
            handler = TA_Handler(
                symbol="XAUUSD",
                exchange=src["exchange"],
                screener=src["screener"],
                interval=config["interval"]
            )
            analysis = handler.get_analysis()
            ind = analysis.indicators
            
            sar_val = float(ind.get("P.SAR", 0))
            price_val = float(ind.get("close", 0))
            
            if sar_val > 0 and price_val > 0:
                sar_type = "Direnç" if price_val < sar_val else "Destek"
                return price_val, {"sar": sar_val, "type": sar_type, "label": config["name"]}
        except:
            continue
    
    return None, None

@st.cache_data(ttl=5)
def fetch_all_timeframe_sar_data():
    """Tüm zaman dilimleri için SAR verilerini çeker - HER BİRİ BAĞIMSIZ"""
    timeframes = ["1H", "4H", "1D", "1W", "1M"]
    results = {}
    current_price = 0
    
    for tf in timeframes:
        price, sar_data = fetch_sar_for_timeframe(tf)
        if price and sar_data:
            current_price = price
            results[tf] = sar_data
    
    return current_price, results

# ---------------------------------------------------------
# ULUDAĞ METODOLOJİSİNE GÖRE ANALİZ MOTORU
# ---------------------------------------------------------
def analyze_with_uludag_method(price, sar_data, selected_tf):
    """
    Uludağ'ın metodolojisine göre analiz yapar:
    1. Her zaman diliminin SAR'ı bağımsız değerlendirilir
    2. Üstte kalan SAR sayısı hesaplanır (temizlenmemiş dirençler)
    3. Zaman dilimi hiyerarşisi dikkate alınır
    """
    
    analysis = {
        "price": price,
        "selected_tf": selected_tf,
        "selected_tf_sar": sar_data.get(selected_tf, {}),
        "sars_above": {},  # Fiyatın üstündeki SAR'lar (dirençler)
        "sars_below": {},  # Fiyatın altındaki SAR'lar (destekler)
        "total_sars_above": 0,
        "total_sars_below": 0,
        "nearest_resistance": None,
        "nearest_support": None,
        "recommendation": "",
        "reasoning": []
    }
    
    # Her zaman diliminin SAR'ını ayrı ayrı değerlendir
    for tf, data in sar_data.items():
        sar_val = data["sar"]
        sar_type = data["type"]
        
        if sar_val > price:
            analysis["sars_above"][tf] = sar_val
            analysis["total_sars_above"] += 1
        else:
            analysis["sars_below"][tf] = sar_val
            analysis["total_sars_below"] += 1
    
    # En yakın direnç ve destek seviyelerini bul
    if analysis["sars_above"]:
        analysis["nearest_resistance"] = min(analysis["sars_above"].values())
    if analysis["sars_below"]:
        analysis["nearest_support"] = max(analysis["sars_below"].values())
    
    # Uludağ'ın kurallarına göre tavsiye üret
    selected_tf_data = analysis["selected_tf_sar"]
    
    if not selected_tf_data:
        return analysis
    
    selected_tf_sar_val = selected_tf_data.get("sar", 0)
    selected_tf_type = selected_tf_data.get("type", "")
    
    # KURAL 1: Seçilen zaman diliminde direnç altındaysa
    if selected_tf_type == "Direnç":
        analysis["recommendation"] = "BEKLEMEDE KAL"
        analysis["reasoning"].append(f"{selected_tf_data['label']} SAR direnci (${selected_tf_sar_val:.2f}) kırılmadan işlem açılmaz")
        analysis["reasoning"].append(f"Üstte {analysis['total_sars_above']} adet temizlenmemiş SAR direnci var")
        
    # KURAL 2: Seçilen zaman diliminde destekteyse
    else:
        # KURAL 2A: Üstte hiç SAR yoksa (SERİ HAREKET)
        if analysis["total_sars_above"] == 0:
            analysis["recommendation"] = "SERİ HAREKET POTANSİYELİ - POZİSYON KORU/ALIM YAP"
            analysis["reasoning"].append("Üstünde SAR kalmayan enstrüman seri hareket yapar (Uludağ kuralı)")
            analysis["reasoning"].append("Tüm zaman dilimlerinde direnç temizlenmiş")
            
        # KURAL 2B: Üstte SAR varsa ama seçilen TF'de destekteyse
        else:
            analysis["recommendation"] = "TEPKİ YÜKSELİŞİ - KADEMELİ TAKİP"
            analysis["reasoning"].append(f"{selected_tf_data['label']} SAR desteği (${selected_tf_sar_val:.2f}) çalışıyor")
            analysis["reasoning"].append(f"Ancak üst zaman dilimlerinde {analysis['total_sars_above']} adet SAR direnci var")
            analysis["reasoning"].append(f"En yakın direnç: ${analysis['nearest_resistance']:.2f}")
    
    # KURAL 3: Stop-loss seviyesi
    if analysis["nearest_support"]:
        analysis["stop_loss"] = analysis["nearest_support"]
    else:
        # En alttaki SAR stop olur
        all_sars = [data["sar"] for data in sar_data.values()]
        analysis["stop_loss"] = min(all_sars) if all_sars else price * 0.95
    
    return analysis

# ---------------------------------------------------------
# SEKMELER
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "🔥 CANLI ANALİZ & TAVSİYE MOTORU", 
    "📊 TÜM ZAMAN DİLİMLERİ SAR HARİTASI",
    "📖 METODOLOJİ RAPORU"
])

# =========================================================
# SEKME 1: CANLI ANALİZ & TAVSİYE MOTORU
# =========================================================
with tab1:
    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.subheader("⚙️ Analiz Parametreleri")
        selected_tf_label = st.radio(
            "Hangi Zaman Dilimine Göre Analiz Yapılsın?",
            options=["1 Saatlik (1H)", "4 Saatlik (4H)", "1 Günlük (1D)", "1 Haftalık (1W)", "1 Aylık (1M)"],
            index=2,
            help="Seçtiğiniz zaman diliminin SAR'ı birincil karar mekanizması olacaktır"
        )
        
        tf_code_map = {
            "1 Saatlik (1H)": "1H",
            "4 Saatlik (4H)": "4H",
            "1 Günlük (1D)": "1D",
            "1 Haftalık (1W)": "1W",
            "1 Aylık (1M)": "1M"
        }
        
        selected_tf = tf_code_map[selected_tf_label]
        
        if st.button("🔄 VERİLERİ GÜNCELLE VE ANALİZ ET", type="primary", use_container_width=True):
            st.cache_data.clear()

    with col_r:
        tv_widget_html = f"""
        <div class="tradingview-widget-container" style="height:400px;width:100%;">
          <div id="tradingview_chart" style="height:400px;width:100%;"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "OANDA:XAUUSD",
            "interval": "{selected_tf}",
            "timezone": "Europe/Istanbul",
            "theme": "light",
            "style": "1",
            "locale": "tr",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "container_id": "tradingview_chart"
          }});
          </script>
        </div>
        """
        components.html(tv_widget_html, height=410)

    st.divider()

    # VERİLERİ ÇEK VE ANALİZ ET
    try:
        price, sar_data = fetch_all_timeframe_sar_data()
        
        if price > 0:
            # Başlık
            st.subheader(f" CANLI FİYAT: ${price:.2f}")
            st.markdown(f"*Son güncelleme: {datetime.now().strftime('%H:%M:%S')}*")
            
            # TÜM ZAMAN DİLİMLERİNİN SAR DURUMU (Her biri bağımsız)
            st.markdown("### 📊 HER ZAMAN DİLİMİNİN AYRI SAR DURUMU")
            st.info(" **ÖNEMLİ:** Her zaman diliminin kendi mum yapısına göre SAR seviyesi farklıdır ve bağımsız değerlendirilmelidir.")
            
            cols = st.columns(5)
            tf_order = ["1H", "4H", "1D", "1W", "1M"]
            
            for idx, tf in enumerate(tf_order):
                if tf in sar_data:
                    sar_val = sar_data[tf]["sar"]
                    sar_type = sar_data[tf]["type"]
                    label = sar_data[tf]["label"]
                    
                    delta = price - sar_val
                    delta_text = f"{delta:+.2f}"
                    
                    with cols[idx]:
                        if sar_type == "Destek":
                            st.success(f"**{label}**\n\n${sar_val:.2f}\n\n🟢 {delta_text}\n\n**DESTEK**")
                        else:
                            st.error(f"**{label}**\n\n${sar_val:.2f}\n\n🔴 {delta_text}\n\n**DİRENÇ**")
            
            st.divider()
            
            # ANALİZ SONUÇLARI
            analysis = analyze_with_uludag_method(price, sar_data, selected_tf)
            
            st.subheader(f" {selected_tf_label} PERİYODUNA ÖZEL STRATEJİ")
            
            # Özet Metrikler
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Üstteki SAR Sayısı", 
                         f"{analysis['total_sars_above']}", 
                         "Temizlenmemiş Direnç" if analysis['total_sars_above'] > 0 else "Direnç Yok ✓")
            with col2:
                st.metric("Alttaki SAR Sayısı", 
                         f"{analysis['total_sars_below']}", 
                         "Mevcut Destekler")
            with col3:
                if analysis['nearest_resistance']:
                    st.metric("En Yakın Direnç", f"${analysis['nearest_resistance']:.2f}")
                else:
                    st.metric("En Yakın Direnç", "YOK")
            with col4:
                if analysis['nearest_support']:
                    st.metric("En Yakın Destek", f"${analysis['nearest_support']:.2f}")
                else:
                    st.metric("En Yakın Destek", "YOK")
            
            st.divider()
            
            # TAVSİYE KUTUSU
            if analysis['recommendation'] == "BEKLEMEDE KAL":
                st.error(f"### 🔴 TAVSİYE: {analysis['recommendation']}")
            elif analysis['recommendation'] == "SERİ HAREKET POTANSİYELİ - POZİSYON KORU/ALIM YAP":
                st.success(f"### 🟢 TAVSİYE: {analysis['recommendation']}")
            else:
                st.warning(f"### 🟡 TAVSİYE: {analysis['recommendation']}")
            
            # GEREKÇELER
            st.markdown("#### 📝 Analiz Gerekçeleri:")
            for i, reason in enumerate(analysis['reasoning'], 1):
                st.markdown(f"**{i}.** {reason}")
            
            # STOP-LOSS
            st.info(f"### 🛡️ Risk Yönetimi\n\n**Dinamik Stop-Loss Seviyesi:** ${analysis['stop_loss']:.2f}\n\n*Bu seviye, en yakın SAR destek noktasına göre belirlenmiştir.*")
            
            # KONTROL LİSTESİ
            st.divider()
            st.markdown("### ✅ Uludağ Metodolojisi Kontrol Listesi")
            
            col_check1, col_check2 = st.columns(2)
            
            with col_check1:
                st.markdown(f"""
                **Zaman Dilimi Analizi:**
                - {'✓' if analysis['selected_tf_sar'] else '✗'} {selected_tf_label} SAR verisi mevcut
                - {'✓' if analysis['selected_tf_sar'].get('type') == 'Destek' else '✗'} {selected_tf_label} SAR'ı destek konumunda
                - {'✓' if analysis['total_sars_above'] == 0 else '✗'} Üstte temizlenmemiş SAR yok
                """)
            
            with col_check2:
                st.markdown(f"""
                **Risk Kontrolleri:**
                - {'✓' if analysis['nearest_support'] else '✗'} Destek seviyesi belirlendi
                - {'✓' if analysis['total_sars_above'] <= 2 else '✗'} Makul sayıda direnç
                - {'✓' if price > analysis['stop_loss'] else '✗'} Fiyat stop üstünde
                """)
            
            # EK BİLGİLER
            with st.expander("📚 Detaylı Zaman Dilimi Analizi"):
                st.markdown("#### Her Zaman Diliminin Bağımsız Değerlendirmesi:")
                
                for tf in tf_order:
                    if tf in sar_data:
                        data = sar_data[tf]
                        st.markdown(f"""
                        **{data['label']} ({tf}):**
                        - SAR Seviyesi: ${data['sar']:.2f}
                        - Konum: **{data['type']}**
                        - Fiyat Farkı: ${price - data['sar']:+.2f}
                        """)
                        
                        if data['type'] == "Direnç":
                            st.warning(f"→ {data['label']} SAR direnci kırılmadan bu periyotta yükseliş beklenmez.")
                        else:
                            st.success(f"→ {data['label']} SAR desteği korunuyor, bu periyotta pozitif.")
                        
                        st.divider()
        
        else:
            st.error("Veri çekilemedi. Lütfen bağlantınızı kontrol edin veya daha sonra tekrar deneyin.")
    
    except Exception as e:
        st.error(f"Analiz yapılırken hata oluştu: {str(e)}")
        st.exception(e)

# =========================================================
# SEKME 2: TÜM ZAMAN DİLİMLERİ SAR HARİTASI
# =========================================================
with tab2:
    st.header(" TÜM ZAMAN DİLİMLERİ SAR HARİTASI")
    
    st.markdown("""
    ### Uludağ Metodolojisi: Zaman Dilimi Hiyerarşisi
    
    **Temel Prensip:** Her zaman diliminin kendi SAR seviyesi vardır ve bunlar **birbirinden bağımsız** değerlendirilmelidir.
    
    **Hiyerarşi Kuralı:**
    1. Aylık SAR çok uzaktaysa → Haftalık SAR'a bak
    2. Haftalık SAR çok uzaktaysa → Günlük SAR'a bak
    3. Seçilen zaman dilimindeki SAR kırılmadan işlem yapılmaz
    """)
    
    try:
        price, sar_data = fetch_all_timeframe_sar_data()
        
        if price > 0:
            # Tablo formatında gösterim
            st.markdown("### Tüm Zaman Dilimleri SAR Özeti")
            
            table_data = []
            for tf in ["1H", "4H", "1D", "1W", "1M"]:
                if tf in sar_data:
                    data = sar_data[tf]
                    table_data.append({
                        "Zaman Dilimi": data["label"],
                        "SAR Seviyesi": f"${data['sar']:.2f}",
                        "Konum": "🟢 Destek" if data["type"] == "Destek" else "🔴 Direnç",
                        "Fiyat Farkı": f"${price - data['sar']:+.2f}",
                        "Durum": "Aktif" if abs(price - data['sar']) / price < 0.05 else "Uzak"
                    })
            
            st.table(table_data)
            
            # Görsel Harita
            st.markdown("### Görsel SAR Haritası")
            
            # Basit bir görsel gösterim
            min_sar = min(data["sar"] for data in sar_data.values())
            max_sar = max(data["sar"] for data in sar_data.values())
            range_size = max_sar - min_sar
            
            st.markdown(f"""
            **Fiyat:** ${price:.2f}
            
            **SAR Aralığı:** ${min_sar:.2f} - ${max_sar:.2f}
            """)
            
            # Her SAR seviyesini görselleştir
            for tf in ["1M", "1W", "1D", "4H", "1H"]:
                if tf in sar_data:
                    data = sar_data[tf]
                    distance_from_price = abs(price - data["sar"]) / price * 100
                    
                    bar_color = "🟢" if data["type"] == "Destek" else ""
                    position = "ALT" if data["type"] == "Destek" else "ÜST"
                    
                    st.markdown(f"""
                    {bar_color} **{data['label']}** (${data['sar']:.2f}) - Fiyatın {position}ında - Mesafe: %{distance_from_price:.2f}
                    """)
                    
                    # Progress bar ile görsel
                    if data["type"] == "Destek":
                        progress_val = (data["sar"] - min_sar) / range_size if range_size > 0 else 0
                    else:
                        progress_val = (data["sar"] - min_sar) / range_size if range_size > 0 else 0
                    
                    st.progress(progress_val)
            
        else:
            st.error("Veri çekilemedi.")
    
    except Exception as e:
        st.error(f"Hata: {str(e)}")

# =========================================================
# SEKME 3: METODOLOJİ RAPORU
# =========================================================
with tab3:
    st.header("📖 ONS PİYASASI TEMEL SAR ANALİZ RAPORU")
    
    st.markdown("""
    ## Emrah Uludağ SAR Metodolojisi - Ons Piyasası İçin
    
    ### 1. Temel Felsefe: SAR Bir "Harita"dır
    Ons piyasasında SAR, basit bir "al-sat" oku olarak değil; fiyatın çekim alanını, trendin sağlamlığını ve risk yönetimi sınırlarını gösteren **dinamik bir harita** olarak ele alınmalıdır.
    
    ### 2. Zaman Dilimi Hiyerarşisi (EN ÖNEMLİ KURAL)
    
    **Her zaman diliminin kendi SAR'ı BAĞIMSIZDIR:**
    - **1 Saatlik (1H) SAR:** Kısa vadeli düzeltmeleri gösterir
    - **4 Saatlik (4H) SAR:** Orta vadeli trendi gösterir
    - **Günlük (1D) SAR:** Ana trend yönünü gösterir
    - **Haftalık (1W) SAR:** Orta-uzun vadeli destek/dirençleri gösterir
    - **Aylık (1M) SAR:** Uzun vadeli ana hedefleri gösterir
    
    **Kural:** Aylık SAR fiyata çok uzaktaysa, haftalık SAR'a bakılır. Haftalık da uzaksa, günlük SAR takip edilir.
    
    ### 3. "Üstünde SAR Bırakmama" Prensibi
    
    Bir enstrümanın seri ve güçlü hareket yapabilmesi için, fiyatın üzerindeki SAR dirençlerini temizlemiş olması gerekir.
    
    - **Üstte SAR yoksa:** Seri hareket beklenir
    - **Üstte birden fazla SAR varsa:** Yükseliş yavaşlar, düzeltme yapar
    
    ### 4. SAR Kümelenmesi (Birleşme) Sinyali
    
    Grafikte SAR noktalarının alt alta veya yan yana sıkışması:
    - Trendin momentum kaybettiğini
    - Piyasanın kararsız olduğunu
    - Trend dönüşü yaklaştığını gösterir
    
    ### 5. Dinamik Destek/Direnç Yönetimi
    
    SAR seviyeleri statik değildir:
    - Yükseliş trendinde, en alttaki SAR "dinamik destek"tir
    - Her periyotta bu seviye yukarı güncellenir
    - Stop-loss, bu dinamik SAR noktasının altına konur
    
    ### 6. İki Altın Kural
    
    **KURAL 1:** Seçilen zaman dilimindeki SAR direnci kırılmadan işlem açılmaz.
    
    **KURAL 2:** Üst zaman dilimlerindeki SAR'lar da dikkate alınır. Günlükte destek olsa bile, haftalıkta direnç varsa yükseliş sınırlı kalır.
    
    ### 7. Risk Yönetimi
    
    - **Stop-Loss:** En yakın SAR destek seviyesinin hemen altı
    - **Kâr Al:** Bir üst SAR direnç seviyesi
    - **Disiplin:** SAR seviyelerini "umut" ile değil, "disiplin" ile takip et
    
    ---
    
    *Not: Bu metodoloji, Uludağ'ın paylaşımlarından derlenmiştir ve yatırım tavsiyesi değildir.*
    """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
<p>Bu uygulama, Emrah Uludağ'ın SAR analiz metodolojisine göre hazırlanmıştır.</p>
<p><b>Yasal Uyarı:</b> Bu araç yatırım tavsiyesi değildir. Kendi araştırmanızı yapınız.</p>
</div>
""", unsafe_allow_html=True)
