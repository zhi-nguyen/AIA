/**
 * useUserProfile.ts - Hook quản lý profile người dùng
 * Load profile on mount, save on submit
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { getUserProfile, createUserProfile, type UserProfile } from "@/lib/api";

interface ProfileFormState {
  name: string;
  occupation: string;
  address: string;
  interests: string[];
  preferred_news_sources: string[];
  work_style: string;
}

const DEFAULT_STATE: ProfileFormState = {
  name: "",
  occupation: "",
  address: "",
  interests: [],
  preferred_news_sources: [],
  work_style: "",
};

export function useUserProfile() {
  const [profile, setProfile] = useState<ProfileFormState>(DEFAULT_STATE);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasProfile, setHasProfile] = useState(false);

  // Load profile on mount
  useEffect(() => {
    const load = async () => {
      try {
        setIsLoading(true);
        const res = await getUserProfile();
        if (res.profile) {
          setProfile({
            name: res.profile.name || "",
            occupation: res.profile.occupation || "",
            address: res.profile.address || "",
            interests: res.profile.interests || [],
            preferred_news_sources: res.profile.preferred_news_sources || [],
            work_style: res.profile.work_style || "",
          });
          setHasProfile(true);
        }
      } catch {
        // Profile chưa có hoặc backend chưa sẵn sàng
        console.log("[Profile] Chưa có profile hoặc không kết nối được backend");
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  const updateField = useCallback(<K extends keyof ProfileFormState>(
    field: K,
    value: ProfileFormState[K]
  ) => {
    setProfile((prev) => ({ ...prev, [field]: value }));
    setIsSaved(false);
  }, []);

  const saveProfile = useCallback(async () => {
    if (!profile.name.trim()) {
      setError("Vui lòng nhập tên của bạn");
      return false;
    }

    setError(null);
    setIsSaving(true);

    try {
      await createUserProfile({
        name: profile.name.trim(),
        occupation: profile.occupation.trim(),
        address: profile.address.trim(),
        interests: profile.interests,
        preferred_news_sources: profile.preferred_news_sources,
        work_style: profile.work_style.trim(),
      });

      setIsSaved(true);
      setHasProfile(true);
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Lỗi không xác định";
      setError(msg);
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [profile]);

  return {
    profile,
    isLoading,
    isSaving,
    isSaved,
    error,
    hasProfile,
    updateField,
    saveProfile,
  };
}
