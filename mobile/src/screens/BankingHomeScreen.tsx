import React, { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { api, BankingSummary } from "../api/client";
import { colors, styles as s } from "../theme";

export function BankingHomeScreen({ navigation }: any) {
  const [summary, setSummary] = useState<BankingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.bankingSummary();
      setSummary(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) {
    return (
      <View style={[s.screen, { justifyContent: "center", alignItems: "center" }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const totalBalance = (summary?.connections || []).reduce((sum, c) => sum + (c.balance || 0), 0);

  return (
    <ScrollView style={s.screen} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {/* Balance Card */}
      <View style={balanceCard}>
        <Text style={balanceLabel}>Total Balance</Text>
        <Text style={balanceAmount}>₹{totalBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</Text>
        <View style={actionRow}>
          <ActionBtn icon="+" label="Add" onPress={() => {}} />
          <ActionBtn icon="↗" label="Send" onPress={() => navigation.navigate("BankingTransfer")} />
          <ActionBtn icon="📱" label="UPI" onPress={() => navigation.navigate("BankingTransfer")} />
          <ActionBtn icon="📄" label="Bills" onPress={() => navigation.navigate("BankingBills")} />
        </View>
      </View>

      {/* Quick Actions */}
      <Text style={sectionTitle}>Quick Actions</Text>
      <View style={quickGrid}>
        <QuickAction icon="🏦" label="Link Bank" onPress={() => navigation.navigate("BankingConnect")} />
        <QuickAction icon="👥" label="Beneficiaries" onPress={() => navigation.navigate("BankingBeneficiaries")} />
        <QuickAction icon="💸" label="Transfer" onPress={() => navigation.navigate("BankingTransfer")} />
        <QuickAction icon="⚡" label="Electricity" onPress={() => navigation.navigate("BankingBills", { category: "electricity" })} />
        <QuickAction icon="📱" label="Recharge" onPress={() => navigation.navigate("BankingBills", { category: "mobile" })} />
        <QuickAction icon="📡" label="DTH" onPress={() => navigation.navigate("BankingBills", { category: "dth" })} />
        <QuickAction icon="🔥" label="Gas" onPress={() => navigation.navigate("BankingBills", { category: "gas" })} />
        <QuickAction icon="📋" label="History" onPress={() => navigation.navigate("BankingHistory")} />
      </View>

      {/* Connected Banks */}
      <Text style={sectionTitle}>Connected Banks</Text>
      {(summary?.connections || []).length === 0 ? (
        <View style={[s.card, { alignItems: "center", padding: 24 }]}>
          <Text style={{ color: colors.muted, marginBottom: 12 }}>No banks connected</Text>
          <Pressable style={s.button} onPress={() => navigation.navigate("BankingConnect")}>
            <Text style={s.buttonText}>Connect Your Bank</Text>
          </Pressable>
        </View>
      ) : (
        summary?.connections.map((conn) => (
          <View key={conn.id} style={bankCard}>
            <View style={bankHeader}>
              <View style={bankLogo}>
                <Text style={{ color: "#fff", fontWeight: "700" }}>{conn.bank_name.slice(0, 2)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "600" }}>{conn.bank_name}</Text>
                <Text style={{ color: colors.muted, fontSize: 12 }}>••••{conn.account_number.slice(-4)}</Text>
              </View>
              <View style={[statusBadge, { backgroundColor: conn.status === "active" ? "#d4edda" : "#fff3cd" }]}>
                <Text style={{ fontSize: 11, fontWeight: "600", color: conn.status === "active" ? "#155724" : "#856404" }}>{conn.status}</Text>
              </View>
            </View>
            <View style={{ padding: 12 }}>
              <Text style={{ color: colors.muted, fontSize: 12 }}>Balance</Text>
              <Text style={{ fontSize: 20, fontWeight: "700" }}>₹{(conn.balance || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</Text>
            </View>
          </View>
        ))
      )}

      {/* UPI IDs */}
      {(summary?.upi_ids || []).length > 0 && (
        <>
          <Text style={sectionTitle}>Your UPI IDs</Text>
          {summary?.upi_ids.map((upi) => (
            <View key={upi.id} style={[s.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
              <Text style={{ fontSize: 20 }}>📱</Text>
              <Text style={{ fontWeight: "600", flex: 1 }}>{upi.upi_id}</Text>
              {upi.is_primary === 1 && (
                <View style={{ backgroundColor: colors.primary, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 }}>
                  <Text style={{ color: "#fff", fontSize: 11, fontWeight: "600" }}>Primary</Text>
                </View>
              )}
            </View>
          ))}
        </>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function ActionBtn({ icon, label, onPress }: { icon: string; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={actionBtn}>
      <Text style={{ fontSize: 20 }}>{icon}</Text>
      <Text style={{ color: "#fff", fontSize: 11, marginTop: 2 }}>{label}</Text>
    </Pressable>
  );
}

function QuickAction({ icon, label, onPress }: { icon: string; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={quickItem}>
      <Text style={{ fontSize: 24 }}>{icon}</Text>
      <Text style={{ fontSize: 11, color: colors.muted, marginTop: 4 }}>{label}</Text>
    </Pressable>
  );
}

const balanceCard = {
  background: "linear-gradient(135deg, #667eea, #764ba2)" as any,
  backgroundColor: "#6c5ce7",
  borderRadius: 16,
  padding: 24,
  marginBottom: 20,
} as any;

const balanceLabel = { color: "rgba(255,255,255,0.9)", fontSize: 14 } as const;
const balanceAmount = { color: "#fff", fontSize: 32, fontWeight: "700" as const, marginVertical: 8 };
const actionRow = { flexDirection: "row" as const, gap: 8, marginTop: 8 };
const actionBtn = {
  flex: 1, backgroundColor: "rgba(255,255,255,0.2)", borderRadius: 12,
  padding: 12, alignItems: "center" as const,
};
const sectionTitle = { fontSize: 18, fontWeight: "600" as const, marginBottom: 12, marginTop: 8 };
const quickGrid = { flexDirection: "row" as const, flexWrap: "wrap" as const, gap: 8, marginBottom: 20 };
const quickItem = {
  width: "23%" as any, backgroundColor: "#fff", borderRadius: 14, padding: 14,
  alignItems: "center" as const, shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
};
const bankCard = { backgroundColor: "#fff", borderRadius: 14, marginBottom: 10, overflow: "hidden" as const };
const bankHeader = { flexDirection: "row" as const, alignItems: "center" as const, gap: 12, padding: 12, backgroundColor: "#fafafa", borderBottomWidth: 1, borderBottomColor: "#eee" };
const bankLogo = { backgroundColor: colors.primary, width: 40, height: 40, borderRadius: 10, alignItems: "center" as const, justifyContent: "center" as const };
const statusBadge = { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 };