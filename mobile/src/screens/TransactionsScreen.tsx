import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { api, Transaction } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatMoney, styles } from "../theme";

export function TransactionsScreen() {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("Groceries");
  const [error, setError] = useState("");

  const load = async () => {
    const { transactions: rows } = await api.transactions();
    setTransactions(rows);
  };

  useEffect(() => {
    load().catch(console.error);
  }, []);

  const addTransaction = async () => {
    setError("");
    const value = parseFloat(amount);
    if (!description || !value || value <= 0) {
      setError("Enter a description and valid amount.");
      return;
    }
    try {
      await api.createTransaction({
        description,
        amount: value,
        category,
        type: "expense",
        transaction_date: new Date().toISOString().slice(0, 10),
      });
      setDescription("");
      setAmount("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add transaction");
    }
  };

  const currency = user?.currency || "USD";

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.title}>Transactions</Text>

      <View style={styles.card}>
        <TextInput style={styles.input} placeholder="Description" value={description} onChangeText={setDescription} />
        <TextInput style={styles.input} placeholder="Amount" keyboardType="decimal-pad" value={amount} onChangeText={setAmount} />
        <TextInput style={styles.input} placeholder="Category" value={category} onChangeText={setCategory} />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable style={styles.button} onPress={addTransaction}>
          <Text style={styles.buttonText}>Add expense</Text>
        </Pressable>
      </View>

      {transactions.map((txn) => (
        <View key={txn.id} style={styles.card}>
          <View style={styles.row}>
            <Text style={{ fontWeight: "600", flex: 1 }}>{txn.description}</Text>
            <Text>{formatMoney(txn.amount, currency)}</Text>
          </View>
          <Text style={styles.cardLabel}>{txn.type} · {txn.category}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
