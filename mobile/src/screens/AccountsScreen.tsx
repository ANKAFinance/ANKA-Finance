import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { api, Account } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatMoney, styles } from "../theme";

export function AccountsScreen() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<Account[]>([]);

  useEffect(() => {
    api.accounts().then(({ accounts: rows }) => setAccounts(rows)).catch(console.error);
  }, []);

  const currency = user?.currency || "USD";

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.title}>Accounts</Text>
      {accounts.map((account) => (
        <View key={account.id} style={styles.card}>
          <View style={styles.row}>
            <Text style={{ fontWeight: "600" }}>{account.name}</Text>
            <Text style={styles.cardValue}>{formatMoney(account.balance, currency)}</Text>
          </View>
          <Text style={styles.cardLabel}>{account.type}</Text>
        </View>
      ))}
      {accounts.length === 0 && <Text style={styles.subtitle}>No accounts yet. Add them from the web app or future mobile form.</Text>}
    </ScrollView>
  );
}
