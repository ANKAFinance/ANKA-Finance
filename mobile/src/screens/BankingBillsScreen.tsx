import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api, Account, Biller } from "../api/client";
import { colors, styles as s } from "../theme";

const CATEGORIES: Record<string, string> = {
  electricity: "⚡ Electricity", mobile: "📱 Mobile", dth: "📡 DTH",
  broadband: "🌐 Broadband", gas: "🔥 Gas", insurance: "🛡️ Insurance",
  fastag: "🚗 FASTag", creditcard: "💳 Credit Card", water: "💧 Water",
};

export function BankingBillsScreen({ navigation, route }: any) {
  const initialCategory = route?.params?.category || "electricity";
  const [category, setCategory] = useState(initialCategory);
  const [billers, setBillers] = useState<Biller[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedBiller, setSelectedBiller] = useState<Biller | null>(null);
  const [consumerNumber, setConsumerNumber] = useState("");
  const [fromAccountId, setFromAccountId] = useState<number>(0);
  const [amount, setAmount] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.bankingBillers(category), api.accounts()]).then(([b, a]) => {
      setBillers(b.billers || []);
      setAccounts(a.accounts);
      if (a.accounts.length > 0) setFromAccountId(a.accounts[0].id);
    });
  }, [category]);

  const fetchBill = async () => {
    if (!selectedBiller || !consumerNumber) { Alert.alert("Error", "Select biller and enter consumer number"); return; }
    try {
      const result = await api.bankingFetchBill({ biller_code: selectedBiller.biller_code, consumer_number: consumerNumber });
      setAmount(result.bill.amount.toString());
      Alert.alert("Bill Found", `Amount: ₹${result.bill.amount}\nDue: ${result.bill.due_date}`);
    } catch { Alert.alert("Error", "Could not fetch bill"); }
  };

  const pay = async () => {
    if (!selectedBiller || !consumerNumber || !amount) { setError("Fill all fields"); return; }
    setError(""); setBusy(true);
    try {
      const result = await api.bankingPayBill({
        biller_code: selectedBiller.biller_code,
        biller_name: selectedBiller.name,
        consumer_number: consumerNumber,
        amount: parseFloat(amount),
        from_account_id: fromAccountId,
      });
      Alert.alert("Payment Successful!", result.message, [{ text: "Done", onPress: () => navigation.navigate("BankingHome") }]);
    } catch (e: any) {
      setError(e.message || "Payment failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={s.screen}>
      <Pressable onPress={() => navigation.goBack()}>
        <Text style={{ color: colors.primary, marginBottom: 16, fontWeight: "600" }}>← Back</Text>
      </Pressable>
      <Text style={s.title}>Pay Bills</Text>

      {/* Category tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {Object.entries(CATEGORIES).map(([key, label]) => (
            <Pressable key={key} onPress={() => setCategory(key)} style={{
              padding: 10, borderRadius: 10, borderWidth: 2,
              borderColor: category === key ? colors.primary : colors.line,
              backgroundColor: category === key ? "#f0f0ff" : "#fff",
            }}>
              <Text style={{ fontSize: 13, fontWeight: "600", color: category === key ? colors.primary : colors.muted }}>{label}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>

      {/* Billers grid */}
      <Text style={{ fontWeight: "600", marginBottom: 8 }}>Select Biller</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
        {billers.map((b) => (
          <Pressable key={b.biller_code} onPress={() => setSelectedBiller(b)} style={{
            width: "30%" as any, padding: 16, borderRadius: 12, backgroundColor: "#fff",
            alignItems: "center", borderWidth: 2,
            borderColor: selectedBiller?.biller_code === b.biller_code ? colors.primary : colors.line,
          }}>
            <Text style={{ fontSize: 28 }}>{b.logo}</Text>
            <Text style={{ fontSize: 11, textAlign: "center", marginTop: 4, fontWeight: "500" }}>{b.name}</Text>
          </Pressable>
        ))}
      </View>

      {selectedBiller && (
        <>
          <View style={[s.card, { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 16 }]}>
            <Text style={{ fontSize: 32 }}>{selectedBiller.logo}</Text>
            <Text style={{ fontWeight: "600", fontSize: 16 }}>{selectedBiller.name}</Text>
          </View>

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Consumer Number</Text>
          <TextInput style={s.input} placeholder="Enter consumer number" value={consumerNumber} onChangeText={setConsumerNumber} />

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>From Account</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
            {accounts.map((acc) => (
              <Pressable key={acc.id} onPress={() => setFromAccountId(acc.id)} style={{
                padding: 10, borderRadius: 8, borderWidth: 2,
                borderColor: fromAccountId === acc.id ? colors.primary : colors.line,
              }}>
                <Text style={{ fontSize: 12, fontWeight: "600" }}>{acc.name}</Text>
                <Text style={{ fontSize: 11, color: colors.muted }}>₹{acc.balance.toLocaleString("en-IN")}</Text>
              </Pressable>
            ))}
          </View>

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Amount (₹)</Text>
          <TextInput style={[s.input, { fontSize: 24, fontWeight: "700", textAlign: "center" }]} placeholder="0.00" keyboardType="decimal-pad" value={amount} onChangeText={setAmount} />

          <Pressable onPress={fetchBill} style={{ marginBottom: 12 }}>
            <Text style={{ color: colors.primary, textAlign: "center" }}>🔄 Fetch bill amount automatically</Text>
          </Pressable>

          {error ? <Text style={s.error}>{error}</Text> : null}
          <Pressable style={s.button} onPress={pay} disabled={busy}>
            <Text style={s.buttonText}>{busy ? "Processing..." : "Pay Bill Now ✅"}</Text>
          </Pressable>
          {busy && <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 12 }} />}
        </>
      )}
    </ScrollView>
  );
}