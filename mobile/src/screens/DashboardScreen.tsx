import React, { useEffect, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { api, DashboardData } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatMoney, styles } from "../theme";

export function DashboardScreen() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const dashboard = await api.dashboard();
    setData(dashboard);
  };

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  const currency = data?.currency || user?.currency || "USD";

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.title}>Dashboard</Text>
      <Text style={styles.subtitle}>Hello, {user?.name}</Text>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Net worth</Text>
        <Text style={styles.cardValue}>{formatMoney(data?.net_worth || 0, currency)}</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>This month net</Text>
        <Text style={styles.cardValue}>{formatMoney(data?.monthly_net || 0, currency)}</Text>
      </View>
      <View style={styles.row}>
        <View style={[styles.card, { flex: 1, marginRight: 6 }]}>
          <Text style={styles.cardLabel}>Income</Text>
          <Text style={styles.cardValue}>{formatMoney(data?.monthly_income || 0, currency)}</Text>
        </View>
        <View style={[styles.card, { flex: 1, marginLeft: 6 }]}>
          <Text style={styles.cardLabel}>Expenses</Text>
          <Text style={styles.cardValue}>{formatMoney(data?.monthly_expenses || 0, currency)}</Text>
        </View>
      </View>

      <Text style={[styles.title, { fontSize: 20, marginTop: 12 }]}>Recent transactions</Text>
      {(data?.recent_transactions || []).map((txn) => (
        <View key={txn.id} style={styles.card}>
          <View style={styles.row}>
            <Text style={{ fontWeight: "600", flex: 1 }}>{txn.description}</Text>
            <Text style={{ color: txn.type === "income" ? "#067647" : "#b42318" }}>
              {txn.type === "income" ? "+" : "-"}
              {formatMoney(txn.amount, currency)}
            </Text>
          </View>
          <Text style={styles.cardLabel}>{txn.category} · {txn.transaction_date}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
