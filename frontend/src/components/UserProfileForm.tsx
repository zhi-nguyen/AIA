/**
 * UserProfileForm.tsx - Form nhập thông tin cá nhân
 * Glassmorphism modal cho phép user thiết lập profile
 */

"use client";

import { useState } from "react";
import { useUserProfile } from "@/hooks/useUserProfile";

interface UserProfileFormProps {
  onClose: () => void;
}

export default function UserProfileForm({ onClose }: UserProfileFormProps) {
  const {
    profile,
    isLoading,
    isSaving,
    isSaved,
    error,
    hasProfile,
    updateField,
    saveProfile,
  } = useUserProfile();

  const [interestInput, setInterestInput] = useState("");
  const [newsSourceInput, setNewsSourceInput] = useState("");

  const handleAddInterest = () => {
    const value = interestInput.trim();
    if (value && !profile.interests.includes(value)) {
      updateField("interests", [...profile.interests, value]);
      setInterestInput("");
    }
  };

  const handleRemoveInterest = (item: string) => {
    updateField("interests", profile.interests.filter((i) => i !== item));
  };

  const handleAddNewsSource = () => {
    const value = newsSourceInput.trim();
    if (value && !profile.preferred_news_sources.includes(value)) {
      updateField("preferred_news_sources", [...profile.preferred_news_sources, value]);
      setNewsSourceInput("");
    }
  };

  const handleRemoveNewsSource = (item: string) => {
    updateField("preferred_news_sources", profile.preferred_news_sources.filter((i) => i !== item));
  };

  const handleTagKeyDown = (
    e: React.KeyboardEvent,
    addFn: () => void
  ) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addFn();
    }
  };

  const handleSave = async () => {
    const success = await saveProfile();
    if (success) {
      setTimeout(() => onClose(), 1200);
    }
  };

  if (isLoading) {
    return (
      <div className="profile-overlay" onClick={onClose}>
        <div className="profile-modal" onClick={(e) => e.stopPropagation()}>
          <div className="profile-loading">
            <div className="typing-indicator">
              <span /><span /><span />
            </div>
            <p>Đang tải thông tin...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-overlay" onClick={onClose}>
      <div className="profile-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="profile-modal__header">
          <div>
            <h2 className="profile-modal__title">
              {hasProfile ? "Cập nhật thông tin" : "Thiết lập thông tin cá nhân"}
            </h2>
            <p className="profile-modal__desc">
              Giúp AIA hiểu bạn hơn để phục vụ tốt hơn
            </p>
          </div>
          <button className="profile-modal__close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Form */}
        <div className="profile-form">
          {/* Tên */}
          <div className="profile-field">
            <label className="profile-label">
              Tên của bạn <span className="profile-required">*</span>
            </label>
            <input
              id="profile-name"
              className="profile-input"
              type="text"
              placeholder="Nhập tên..."
              value={profile.name}
              onChange={(e) => updateField("name", e.target.value)}
            />
          </div>

          {/* Nghề nghiệp */}
          <div className="profile-field">
            <label className="profile-label">Nghề nghiệp</label>
            <input
              id="profile-occupation"
              className="profile-input"
              type="text"
              placeholder="VD: Kỹ sư phần mềm, Sinh viên..."
              value={profile.occupation}
              onChange={(e) => updateField("occupation", e.target.value)}
            />
          </div>

          {/* Sở thích */}
          <div className="profile-field">
            <label className="profile-label">Sở thích</label>
            <div className="tag-input-wrapper">
              <div className="tag-list">
                {profile.interests.map((tag) => (
                  <span key={tag} className="profile-tag">
                    {tag}
                    <button
                      className="profile-tag__remove"
                      onClick={() => handleRemoveInterest(tag)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="tag-input-row">
                <input
                  id="profile-interest-input"
                  className="profile-input profile-input--tag"
                  type="text"
                  placeholder="Thêm sở thích (Enter)"
                  value={interestInput}
                  onChange={(e) => setInterestInput(e.target.value)}
                  onKeyDown={(e) => handleTagKeyDown(e, handleAddInterest)}
                />
                <button
                  className="tag-add-btn"
                  onClick={handleAddInterest}
                  disabled={!interestInput.trim()}
                >
                  +
                </button>
              </div>
            </div>
          </div>

          {/* Nguồn tin ưa thích */}
          <div className="profile-field">
            <label className="profile-label">Nguồn tin ưa thích</label>
            <div className="tag-input-wrapper">
              <div className="tag-list">
                {profile.preferred_news_sources.map((tag) => (
                  <span key={tag} className="profile-tag profile-tag--news">
                    {tag}
                    <button
                      className="profile-tag__remove"
                      onClick={() => handleRemoveNewsSource(tag)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="tag-input-row">
                <input
                  id="profile-news-input"
                  className="profile-input profile-input--tag"
                  type="text"
                  placeholder="Thêm nguồn tin (Enter)"
                  value={newsSourceInput}
                  onChange={(e) => setNewsSourceInput(e.target.value)}
                  onKeyDown={(e) => handleTagKeyDown(e, handleAddNewsSource)}
                />
                <button
                  className="tag-add-btn"
                  onClick={handleAddNewsSource}
                  disabled={!newsSourceInput.trim()}
                >
                  +
                </button>
              </div>
            </div>
          </div>

          {/* Phong cách làm việc */}
          <div className="profile-field">
            <label className="profile-label">Phong cách làm việc</label>
            <input
              id="profile-workstyle"
              className="profile-input"
              type="text"
              placeholder="VD: Tập trung sáng, sáng tạo chiều..."
              value={profile.work_style}
              onChange={(e) => updateField("work_style", e.target.value)}
            />
          </div>
        </div>

        {/* Error */}
        {error && <div className="profile-error">{error}</div>}

        {/* Success */}
        {isSaved && (
          <div className="profile-success">
            ✅ Đã lưu thành công! AIA sẽ ghi nhớ thông tin của bạn.
          </div>
        )}

        {/* Actions */}
        <div className="profile-actions">
          <button className="profile-cancel-btn" onClick={onClose}>
            Hủy
          </button>
          <button
            id="profile-save-btn"
            className="profile-save-btn"
            onClick={handleSave}
            disabled={isSaving || !profile.name.trim()}
          >
            {isSaving ? "Đang lưu..." : hasProfile ? "Cập nhật" : "Lưu thông tin"}
          </button>
        </div>
      </div>
    </div>
  );
}
