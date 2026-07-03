import streamlit as st
import plotly.express as px
from db import get_appliance_count, get_today_recommendations
from energy import get_price_summary


def render_dashboard(price_df):
    st.header("Modernes Smart Energy Dashboard")
    summary = get_price_summary(price_df)
    if not summary:
        st.warning("Marktdaten sind derzeit nicht verfügbar.")
        return

    appliance_count = get_appliance_count()
    today_recs = get_today_recommendations()

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Aktueller Preis", f"{summary['current_price']:.2f} €/kWh")
    metric_col2.metric("Günstigste Stunde", summary["cheapest_hour"].strftime("%H:%M"))
    metric_col3.metric("Teuerste Stunde", summary["expensive_hour"].strftime("%H:%M"))
    metric_col4.metric("Tägliche Kosten (1 kWh)", f"{summary['estimated_daily_cost']:.2f} €")

    status_col1, status_col2 = st.columns(2)
    status_col1.metric("Registrierte Geräte", str(appliance_count))
    status_col2.metric("Empfehlungen heute", str(len(today_recs)))

    if not price_df.empty:
        chart_df = price_df.reset_index().rename(columns={"start": "Zeit", "price_eur": "Preis (€)"})
        fig = px.line(chart_df, x="Zeit", y="Preis (€)", title="Strompreis-Verlauf", markers=True)
        fig.update_layout(margin={"l": 10, "r": 10, "t": 40, "b": 10}, height=380)
        st.plotly_chart(fig, use_container_width=True)

    if not today_recs.empty:
        with st.expander("Empfehlungen für heute", expanded=True):
            st.dataframe(today_recs)
    else:
        st.info("Es liegen noch keine Empfehlungen für heute vor.")
