import React, { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api } from "../api/client";
import { colors, styles as s } from "../theme";

const SUPPORTED_BANKS = ["ICICI", "HDFC", "SBI", "AXIS", "Kotak Mahindra", "Yes Bank", "PNB"];

export function BankingConnectScreen({ navigation }: any) {
  const [step, setStep] = useState<"select" | "form" | "connecting">("select");
  const [selectedBank, setSelectedBank] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [accountType, setAccountType] = useState("savings");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const connect = async () => {
    if (!selectedBank || !accountNumber) {
      setError("Please fill all fields");
      return;
    }
    setError("");
    setBusy(true);
    setStep("connecting");
    try {
      const result = await api.bankingConnect({
        bank_name: selectedBank,
        account_number: accountNumber,
        ifsc: ifsc,
        account_type: accountType,
      });
      Alert.alert(
        "Bank Linked! 🎉",
        `${result.message}\n\nUPI ID: ${result.upi_id}\nTransactions imported: ${result.transactions_imported}`,
        [{ text: "Go to Banking", onPress: () => navigation.navigate("BankingHome") }]
      );
    } catch (e: any) {
      setError(e.message || "Connection failed");
      setStep("form");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={s.screen}>
      <Pressable onPress={() => navigation.goBack()}>
        <Text style={{ color: colors.primary, marginBottom: 16, fontWeight: "600" }}>← Back</Text>
      </Pressable>
      <Text style={s.title}>Link Bank Account</Text>
      <Text style={s.subtitle}>Connect your real bank via Account Aggregator</Text>

      {step === "select" && (
        <>
          <Text style={{ fontWeight: "600", marginBottom: 12 }}>Select your bank:</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {SUPPORTED_BANKS.map((bank) => (
              <Pressable
                key={bank}
                onPress={() => { setSelectedBank(bank); setStep("form"); }}
                style={{
                  width: "30%" as any, padding: 16, borderRadius: 12,
                  backgroundColor: "#fff", alignItems: "center",
                  borderWidth: 1, borderColor: colors.line, marginBottom: 8,
                }}
              >
                <View style={{ backgroundColor: colors.primary, width: 40, height: 40, borderRadius: 8, alignItems: "center", justifyContent: "center", marginBottom: 8 }}>
                  <Text style={{ color: "#fff", fontWeight: "700" }}>{bank.slice(0, 2)}</Text>
                </View>
                <Text style={{ fontSize: 12, textAlign: "center", fontWeight: "500" }}>{bank}</Text>
              </Pressable>
            ))}
          </View>
        </>
      )}

      {step === "form" && (
        <>
          <View style={[s.card, { marginBottom: 16 }]}>
            <Text style={{ fontWeight: "600", marginBottom: 4 }}>{selectedBank}</Text>
            <Pressable onPress={() => setStep("select")}>
              <Text style={{ color: colors.primary, fontSize: 13 }}>Change bank</Text>
            </Pressable>
          </View>

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Account Number</Text>
          <TextInput style={s.input} placeholder="Enter account number" keyboardType="numeric" value={accountNumber} onChangeText={setAccountNumber} />

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>IFSC Code</Text>
          <TextInput style={s.input} placeholder="e.g., ICIC0001234" autoCapitalize="characters" value={ifsc} onChangeText={setIfsc} />

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Account Type</Text>
          <View style={{ flexDirection: "row", gap: 8, marginBottom: 16 }}>
            {["savings", "current", "salary"].map((t) => (
              <Pressable key={t} onPress={() => setAccountType(t)} style={{
                flex: 1, padding: 12, borderRadius: 10, borderWidth: 2,
                borderColor: accountType === t ? colors.primary : colors.line,
                backgroundColor: accountType === t ? "#f0f0ff" : "#fff",
                alignItems: "center",
              }}>
                <Text style={{ fontWeight: "600", fontSize: 13, color: accountType === t ? colors.primary : colors.muted }}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </Text>
              </Pressable>
            ))}
          </View>

          <View style={{ flexDirection: "row", gap: 12, padding: 14, backgroundColor: "#fff8f0", borderRadius: 10, marginBottom: 16 }}>
            <Text style={{ fontSize: 20 }}>🔒</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: "600", fontSize: 14 }}>Account Aggregator Consent</Text>
              <Text style={{ color: "#666", fontSize: 12 }}>We'll request 1-year consent to fetch your transactions and balance.</Text>
            </View>
          </View>

          {error ? <Text style={s.error}>{error}</Text> : null}

          <Pressable style={s.button} onPress={connect} disabled={busy}>
            <Text style={s.buttonText}>{busy ? "Connecting..." : "Link Account & Auto-Sync"}</Text>
          </Pressable>
        </>
      )}

      {step === "connecting" && (
        <View style={{ alignItems: "center", padding: 40 }}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={{ marginTop: 16, fontWeight: "600" }}>Connecting to {selectedBank}...</Text>
          <Text style={{ color: colors.muted, marginTop: 8, textAlign: "center" }}>
            Creating secure consent, fetching account details, importing transactions...
          </Text>
        </View>
      )}
    </ScrollView>
  );
}