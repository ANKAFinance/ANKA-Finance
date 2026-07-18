import React, { useEffect, useState } from "react";
import { Alert, Linking, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { api, AppMeta } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useSubscriptions } from "../hooks/useSubscriptions";
import { styles } from "../theme";

export function SettingsScreen() {
  const { user, signOut, deleteAccount } = useAuth();
  const { products, subscribe, restorePurchases } = useSubscriptions();
  const plan = user?.effective_plan || user?.plan || "free";
  const [meta, setMeta] = useState<AppMeta | null>(null);
  const [confirmEmail, setConfirmEmail] = useState("");

  useEffect(() => {
    api.meta()
      .then((data) => setMeta(data.app))
      .catch(() => setMeta(null));
  }, []);

  const openUrl = async (url?: string) => {
    if (!url) return;
    await Linking.openURL(url);
  };

  const emailSupport = async () => {
    const email = meta?.support_email || "support@ankafinance.com";
    await Linking.openURL(`mailto:${email}?subject=ANKA%20Finance%20Support`);
  };

  const manageSubscriptions = async () => {
    const url =
      Platform.OS === "ios"
        ? "https://apps.apple.com/account/subscriptions"
        : "https://play.google.com/store/account/subscriptions";
    await Linking.openURL(url);
  };

  const confirmDelete = () => {
    if (!user || confirmEmail.trim().toLowerCase() !== user.email.toLowerCase()) {
      Alert.alert("Email required", "Type your account email before deleting your account.");
      return;
    }
    Alert.alert(
      "Delete account?",
      "This removes your profile and finance records from the active service database.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteAccount();
            } catch (err) {
              Alert.alert("Could not delete account", err instanceof Error ? err.message : "Please try again.");
            }
          },
        },
      ],
    );
  };

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.title}>Settings</Text>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Profile</Text>
        <Text style={styles.cardValue}>{user?.name}</Text>
        <Text style={styles.subtitle}>{user?.email}</Text>
        <Text style={styles.cardLabel}>Currency: {user?.currency}</Text>
        <Text style={styles.cardLabel}>Plan: {plan}</Text>
        <Text style={styles.cardLabel}>Status: {user?.subscription_status}</Text>
      </View>

      {plan === "free" && (
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Upgrade via App Store / Play Store</Text>
          {products.length === 0 ? (
            <>
              <Pressable style={styles.button} onPress={() => subscribe("com.advait.personalfinancetracker.plus.monthly")}>
                <Text style={styles.buttonText}>Subscribe to Plus</Text>
              </Pressable>
              <Pressable style={styles.secondaryButton} onPress={() => subscribe("com.advait.personalfinancetracker.family.monthly")}>
                <Text>Subscribe to Family</Text>
              </Pressable>
            </>
          ) : (
            products.map((product) => (
              <Pressable key={product.productId} style={styles.button} onPress={() => subscribe(product.productId)}>
                <Text style={styles.buttonText}>
                  Subscribe — {product.title || product.productId}
                </Text>
              </Pressable>
            ))
          )}
        </View>
      )}

      <Pressable style={styles.secondaryButton} onPress={signOut}>
        <Text>Sign out</Text>
      </Pressable>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Purchases</Text>
        <Pressable style={styles.secondaryButton} onPress={restorePurchases}>
          <Text>Restore purchases</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={manageSubscriptions}>
          <Text>Manage subscriptions</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Help and legal</Text>
        <Pressable style={styles.secondaryButton} onPress={emailSupport}>
          <Text>Contact support</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={() => openUrl(meta?.privacy_url)}>
          <Text>Privacy policy</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={() => openUrl(meta?.terms_url)}>
          <Text>Terms of service</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Delete account</Text>
        <Text style={styles.subtitle}>Type your email to confirm deletion.</Text>
        <TextInput
          style={styles.input}
          placeholder={user?.email || "Email"}
          autoCapitalize="none"
          keyboardType="email-address"
          value={confirmEmail}
          onChangeText={setConfirmEmail}
        />
        <Pressable style={styles.dangerButton} onPress={confirmDelete}>
          <Text style={styles.buttonText}>Delete account</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
