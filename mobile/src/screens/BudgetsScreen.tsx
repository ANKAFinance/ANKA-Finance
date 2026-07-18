import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { api, Budget } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatMoney, styles } from "../theme";

export function BudgetsScreen() {
  const { user } = useAuth();
  const [budgets, setBudgets] = useState<Budget[]>([]);

  useEffect(() => {
    api.budgets().then(({ budgets: rows }) => setBudgets(rows)).catch(console.error);
  }, []);

  const currency = user?.currency || "USD";

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.title}>Budgets</Text>
      {budgets.map((budget) => {
        const pct = budget.monthly_limit ? Math.min(100, (budget.spent / budget.monthly_limit) * 100) : 0;
        return (
          <View key={budget.id} style={styles.card}>
            <View style={styles.row}>
              <Text style={{ fontWeight: "600" }}>{budget.category}</Text>
              <Text>{formatMoney(budget.spent, currency)} / {formatMoney(budget.monthly_limit, currency)}</Text>
            </View>
            <Text style={styles.cardLabel}>{pct.toFixed(0)}% used this month</Text>
          </View>
        );
      })}
      {budgets.length === 0 && <Text style={styles.subtitle}>No budgets yet.</Text>}
    </ScrollView>
  );
}
