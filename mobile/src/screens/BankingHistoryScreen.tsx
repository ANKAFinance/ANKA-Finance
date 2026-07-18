import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { api, PaymentTransfer, UpiPayment, BillPayment } from "../api/client";
import { colors, styles as s } from "../theme";

type Tab = "transfers" | "upi" | "bills";

export function BankingHistoryScreen({ navigation }: any) {
  const [tab, setTab] = useState<Tab>("transfers");
  const [transfers, setTransfers] = useState<PaymentTransfer[]>([]);
  const [upiPayments, setUpiPayments] = useState<UpiPayment[]>([]);
  const [bills, setBills] = useState<BillPayment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.bankingTransfers(), api.bankingUpiPayments(), api.bankingBillHistory()])
      .then(([t, u, b]) => {
        setTransfers(t.transfers);
        setUpiPayments(u.payments);
        setBills(b.bills);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <View style={[s.screen, { justifyContent: "center", alignItems: "center" }]}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>;
  }

  return (
    <ScrollView style={s.screen}>
      <Pressable onPress={() => navigation.goBack()}>
        <Text style={{ color: colors.primary, marginBottom: 16, fontWeight: "600" }}>← Back</Text>
      </Pressable>
      <Text style={s.title}>Transaction History</Text>

      <View style={{ flexDirection: "row", gap: 8, marginBottom: 20 }}>
        {(["transfers", "upi", "bills"] as const).map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} style={{
            flex: 1, padding: 10, borderRadius: 8, borderWidth: 2,
            borderColor: tab === t ? colors.primary : colors.line,
            backgroundColor: tab === t ? "#f0f0ff" : "#fff", alignItems: "center",
          }}>
            <Text style={{ fontSize: 12, fontWeight: "600", color: tab === t ? colors.primary : colors.muted }}>
              {t === "transfers" ? "Transfers" : t === "upi" ? "UPI" : "Bills"}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "transfers" && transfers.length === 0 && <Text style={{ color: colors.muted, textAlign: "center", padding: 20 }}>No transfers yet</Text>}
      {tab === "transfers" && transfers.map((t) => (
        <View key={t.id} style={[s.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
          <Text style={{ fontSize: 24 }}>💸</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }}>{t.beneficiary_name}</Text>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{t.beneficiary_account.slice(-4)} • {t.initiated_at.slice(0, 10)}</Text>
            {t.utr && <Text style={{ color: "#aaa", fontSize: 10 }}>UTR: {t.utr}</Text>}
          </View>
          <Text style={{ fontWeight: "700", color: colors.danger }}>-₹{t.amount.toLocaleString("en-IN")}</Text>
        </View>
      ))}

      {tab === "upi" && upiPayments.length === 0 && <Text style={{ color: colors.muted, textAlign: "center", padding: 20 }}>No UPI payments yet</Text>}
      {tab === "upi" && upiPayments.map((p) => (
        <View key={p.id} style={[s.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
          <Text style={{ fontSize: 24 }}>📱</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }}>{p.to_upi_id}</Text>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{p.created_at.slice(0, 10)}{p.note ? ` • ${p.note}` : ""}</Text>
          </View>
          <Text style={{ fontWeight: "700", color: colors.danger }}>-₹{p.amount.toLocaleString("en-IN")}</Text>
        </View>
      ))}

      {tab === "bills" && bills.length === 0 && <Text style={{ color: colors.muted, textAlign: "center", padding: 20 }}>No bill payments yet</Text>}
      {tab === "bills" && bills.map((b) => (
        <View key={b.id} style={[s.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
          <Text style={{ fontSize: 24 }}>📄</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }}>{b.biller_name}</Text>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{b.consumer_number} • {b.paid_at.slice(0, 10)}</Text>
          </View>
          <Text style={{ fontWeight: "700", color: colors.danger }}>-₹{b.amount.toLocaleString("en-IN")}</Text>
        </View>
      ))}
    </ScrollView>
  );
}