import { useEffect, useState } from "react";
import { Alert, Platform } from "react-native";
import {
  finishTransaction,
  getAvailablePurchases,
  getSubscriptions,
  initConnection,
  purchaseErrorListener,
  purchaseUpdatedListener,
  requestSubscription,
  Subscription,
  SubscriptionPurchase,
} from "react-native-iap";

import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const PRODUCT_IDS = Platform.select({
  ios: ["com.advait.personalfinancetracker.plus.monthly", "com.advait.personalfinancetracker.family.monthly"],
  android: ["com.advait.personalfinancetracker.plus.monthly", "com.advait.personalfinancetracker.family.monthly"],
  default: [],
}) as string[];

export function useSubscriptions() {
  const { refreshUser } = useAuth();
  const [products, setProducts] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let purchaseUpdate: { remove: () => void } | undefined;
    let purchaseError: { remove: () => void } | undefined;

    (async () => {
      try {
        await initConnection();
        const subs = await getSubscriptions({ skus: PRODUCT_IDS });
        setProducts(subs);

        purchaseUpdate = purchaseUpdatedListener(async (purchase: SubscriptionPurchase) => {
          try {
            await api.verifyMobilePurchase({
              provider: Platform.OS === "ios" ? "apple" : "google",
              product_id: purchase.productId,
              transaction_id: purchase.transactionId || purchase.purchaseToken || "",
              purchase_token: purchase.purchaseToken,
              receipt_data: purchase.transactionReceipt,
            });
            await finishTransaction({ purchase, isConsumable: false });
            await refreshUser();
          } catch (error) {
            Alert.alert("Purchase failed", error instanceof Error ? error.message : "Please try again.");
          }
        });

        purchaseError = purchaseErrorListener((error) => {
          console.warn("Purchase error", error);
          Alert.alert("Purchase error", error?.message || "Please try again.");
        });
      } finally {
        setLoading(false);
      }
    })();

    return () => {
      purchaseUpdate?.remove();
      purchaseError?.remove();
    };
  }, [refreshUser]);

  const subscribe = async (sku: string) => {
    await requestSubscription({ sku });
  };

  const restorePurchases = async () => {
    try {
      const purchases = await getAvailablePurchases();
      for (const purchase of purchases) {
        if (!PRODUCT_IDS.includes(purchase.productId)) continue;
        await api.verifyMobilePurchase({
          provider: Platform.OS === "ios" ? "apple" : "google",
          product_id: purchase.productId,
          transaction_id: purchase.transactionId || purchase.purchaseToken || "",
          purchase_token: purchase.purchaseToken,
          receipt_data: purchase.transactionReceipt,
        });
      }
      await refreshUser();
      Alert.alert("Purchases restored", "Your existing subscriptions were restored.");
    } catch (error) {
      Alert.alert("Could not restore purchases", error instanceof Error ? error.message : "Please try again.");
    }
  };

  return { products, loading, subscribe, restorePurchases, productIds: PRODUCT_IDS };
}
