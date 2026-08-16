import { useEffect, useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { LuCircleCheckBig } from "react-icons/lu";

import {
  getMyGlobalProfile,
  initializeGlobalProfile,
  resetGlobalProfile,
  updateGlobalProfile,
} from "../../services/profile";
import type { GlobalProfileInitRequest, GlobalProfileRead } from "../../types/profile";
import type { HomeOutletContext } from "./HomeSectionPage";

const POST_PROFILE_INIT_REDIRECT_STORAGE_KEY = "postProfileInitRedirect";
const OTHER_OPTION = "Others";
const SUCCESS_TOAST_DISPLAY_MS = 2400;

type ProfileFieldKey = keyof GlobalProfileInitRequest;

type ProfileFieldSelection = {
  selectedOption: string;
  otherValue: string;
};

type ProfileFieldState = Record<ProfileFieldKey, ProfileFieldSelection>;

type ProfileFieldConfig = {
  key: ProfileFieldKey;
  label: string;
  options: string[];
  otherPlaceholder: string;
};

const FIELD_CONFIG: ProfileFieldConfig[] = [
  {
    key: "supportRole",
    label: "支持角色",
    options: ["Coach", "Study partner", "Mentor", "Examiner", OTHER_OPTION],
    otherPlaceholder: "Describe another support role",
  },
  {
    key: "helpStyle",
    label: "帮助方式",
    options: ["Step-by-step", "Concise", "Example-driven", "Reflective", OTHER_OPTION],
    otherPlaceholder: "Describe another help style",
  },
  {
    key: "learningFocus",
    label: "学习重点",
    options: ["Exam prep", "Theory mastery", "Practical problem solving", "Project work", OTHER_OPTION],
    otherPlaceholder: "Describe another learning focus",
  },
  {
    key: "responseTone",
    label: "回应语气",
    options: ["Encouraging", "Direct", "Calm", "Challenging", OTHER_OPTION],
    otherPlaceholder: "Describe another response tone",
  },
];

function createInitialForm(): ProfileFieldState {
  return {
    supportRole: { selectedOption: "", otherValue: "" },
    helpStyle: { selectedOption: "", otherValue: "" },
    learningFocus: { selectedOption: "", otherValue: "" },
    responseTone: { selectedOption: "", otherValue: "" },
  };
}

function profileToForm(profile: GlobalProfileRead): ProfileFieldState {
  const preferences = profile.preferences ?? {};
  return FIELD_CONFIG.reduce<ProfileFieldState>((next, field) => {
    const value = preferences[field.key]?.trim() ?? "";
    const matchedOption = field.options.find(
      (option) => option !== OTHER_OPTION && option.toLowerCase() === value.toLowerCase()
    );
    next[field.key] = {
      selectedOption: matchedOption ?? (value ? OTHER_OPTION : ""),
      otherValue: matchedOption ? "" : value,
    };
    return next;
  }, createInitialForm());
}

function getRedirectTarget() {
  return localStorage.getItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY) || "/home";
}

function resolveFieldValue(field: ProfileFieldSelection) {
  if (field.selectedOption === OTHER_OPTION) {
    return field.otherValue.trim();
  }

  return field.selectedOption.trim();
}

function GlobalProfileInitPage() {
  const navigate = useNavigate();
  const { currentUser } = useOutletContext<HomeOutletContext>();
  const [form, setForm] = useState<ProfileFieldState>(createInitialForm);
  const [existingProfile, setExistingProfile] = useState<GlobalProfileRead | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [overwriteConfirmOpen, setOverwriteConfirmOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [successBehavior, setSuccessBehavior] = useState<"redirect" | "stay">("redirect");

  useEffect(() => {
    if (currentUser.identity !== "Learner") {
      return undefined;
    }

    let cancelled = false;
    setProfileLoading(true);
    setErrorMessage(null);

    getMyGlobalProfile()
      .then((profile) => {
        if (cancelled) {
          return;
        }
        const hasExistingProfile = !profile.isDefaultProfile;
        setExistingProfile(hasExistingProfile ? profile : null);
        setForm(hasExistingProfile ? profileToForm(profile) : createInitialForm());
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "读取学习画像失败。");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProfileLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser.identity]);

  useEffect(() => {
    if (!successMessage) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      if (successBehavior === "redirect") {
        const target = getRedirectTarget();
        localStorage.removeItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY);
        navigate(target, { replace: true });
      } else {
        setSuccessMessage(null);
      }
    }, SUCCESS_TOAST_DISPLAY_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [navigate, successBehavior, successMessage]);

  const payloadPreview = useMemo<GlobalProfileInitRequest>(
    () => ({
      supportRole: resolveFieldValue(form.supportRole),
      helpStyle: resolveFieldValue(form.helpStyle),
      learningFocus: resolveFieldValue(form.learningFocus),
      responseTone: resolveFieldValue(form.responseTone),
    }),
    [form]
  );

  if (currentUser.identity !== "Learner") {
    return null;
  }

  const handleOptionSelect = (fieldKey: ProfileFieldKey, option: string) => {
    setForm((current) => ({
      ...current,
      [fieldKey]: {
        selectedOption: option,
        otherValue: option === OTHER_OPTION ? current[fieldKey].otherValue : "",
      },
    }));
  };

  const handleOtherValueChange = (
    fieldKey: ProfileFieldKey,
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const { value } = event.target;
    setForm((current) => ({
      ...current,
      [fieldKey]: {
        ...current[fieldKey],
        otherValue: value,
      },
    }));
  };

  const handleSkip = () => {
    const target = getRedirectTarget();
    localStorage.removeItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY);
    navigate(target, { replace: true });
  };

  const saveProfile = async () => {
    setErrorMessage(null);
    setOverwriteConfirmOpen(false);
    try {
      setSubmitting(true);
      if (existingProfile) {
        const updatedProfile = await updateGlobalProfile(payloadPreview);
        setExistingProfile(updatedProfile);
        setForm(profileToForm(updatedProfile));
        setSuccessBehavior("stay");
        setSuccessMessage("学习画像已更新。");
        setSubmitting(false);
      } else {
        await initializeGlobalProfile(payloadPreview);
        setSuccessBehavior("redirect");
        setSuccessMessage("学习画像初始化成功。");
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "保存学习画像失败。"
      );
      setSubmitting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (Object.values(payloadPreview).some((value) => value.length === 0)) {
      setErrorMessage("请为每个属性选择一个选项。如果选择其他，请补充简短说明。");
      return;
    }

    if (existingProfile && !overwriteConfirmOpen) {
      setOverwriteConfirmOpen(true);
      return;
    }

    setOverwriteConfirmOpen(false);
    await saveProfile();
  };

  const handleReset = async () => {
    setErrorMessage(null);
    try {
      setResetting(true);
      await resetGlobalProfile();
      setExistingProfile(null);
      setForm(createInitialForm());
      setResetConfirmOpen(false);
      setOverwriteConfirmOpen(false);
      setSuccessBehavior("stay");
      setSuccessMessage("重置成功，已恢复默认画像。");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "重置学习画像失败。");
    } finally {
      setResetting(false);
    }
  };

  return (
    <section className="home-profile-init-page">
      {successMessage ? (
        <div className="home-profile-init-toast" role="status" aria-live="polite">
          <div className="home-profile-init-toast-icon" aria-hidden="true">
            <LuCircleCheckBig size={18} />
          </div>
          <div className="home-profile-init-toast-copy">
            <strong>成功</strong>
            <span>{successMessage}</span>
          </div>
        </div>
      ) : null}

      <div className="home-profile-init-card">
        <div className="home-profile-init-hero">
          <span className="home-content-badge">学生画像</span>
          <h1>{existingProfile ? "编辑学习画像" : "初始化学习画像"}</h1>
          <p>
            {existingProfile
              ? "调整你的偏好后保存，智能助手会使用新的设置。"
              : "一次性设置偏好，让智能助手在之后的学习活动中更稳定地支持你。"}
          </p>
        </div>

        {profileLoading ? (
          <p className="home-profile-init-loading" role="status">正在读取当前学习画像…</p>
        ) : null}

        {existingProfile ? (
          <div className="home-profile-init-warning" role="note">
            <strong>保存提示</strong>
            <p>再次保存会覆盖当前学习画像，保存前会请你确认。</p>
          </div>
        ) : null}

        <form className="home-profile-init-form" onSubmit={handleSubmit}>
          {FIELD_CONFIG.map((field) => {
            const fieldState = form[field.key];
            const isOtherSelected = fieldState.selectedOption === OTHER_OPTION;

            return (
              <fieldset key={field.key} className="home-profile-init-fieldset">
                <legend>{field.label}</legend>

                <div className="home-profile-init-options" role="radiogroup" aria-label={field.label}>
                  {field.options.map((option) => {
                    const selected = fieldState.selectedOption === option;
                    return (
                      <button
                        key={option}
                        type="button"
                        className={`home-profile-init-option ${selected ? "home-profile-init-option-active" : ""}`}
                        onClick={() => handleOptionSelect(field.key, option)}
                        disabled={profileLoading || submitting || resetting}
                        aria-pressed={selected}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>

                {isOtherSelected ? (
                  <label className="home-profile-init-other">
                    <span>其他</span>
                    <input
                      type="text"
                      value={fieldState.otherValue}
                      onChange={(event) => handleOtherValueChange(field.key, event)}
                      placeholder={field.otherPlaceholder}
                      disabled={profileLoading || submitting || resetting}
                    />
                  </label>
                ) : null}
              </fieldset>
            );
          })}

          {errorMessage ? (
            <div className="home-profile-init-error" role="alert">
              {errorMessage}
            </div>
          ) : null}

          {overwriteConfirmOpen ? (
            <div className="home-profile-init-overwrite-confirm" role="alertdialog" aria-label="确认覆盖学习画像">
              <p>
                <strong>确认覆盖当前学习画像？</strong>
                <span>保存后会使用当前填写内容替换现有画像。</span>
              </p>
              <div className="home-profile-init-overwrite-actions">
                <button
                  type="button"
                  className="home-profile-init-secondary"
                  onClick={() => setOverwriteConfirmOpen(false)}
                  disabled={submitting || resetting}
                >
                  返回修改
                </button>
                <button
                  type="button"
                  className="home-profile-init-primary"
                  onClick={() => void saveProfile()}
                  disabled={submitting || resetting}
                >
                  {submitting ? "正在保存…" : "确认覆盖并保存"}
                </button>
              </div>
            </div>
          ) : null}

          <div className="home-profile-init-reset">
            {resetConfirmOpen ? (
              <div className="home-profile-init-reset-confirm" role="alertdialog" aria-label="确认重置学习画像">
                <p>
                  {existingProfile
                    ? "确认重置当前学习画像吗？"
                    : "确认清空当前填写内容吗？"}
                </p>
                <div className="home-profile-init-reset-confirm-actions">
                  <button
                    type="button"
                    className="home-profile-init-secondary"
                    onClick={() => setResetConfirmOpen(false)}
                    disabled={resetting || submitting}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className="home-profile-init-danger"
                    onClick={handleReset}
                    disabled={resetting || submitting}
                  >
                    {resetting ? "正在重置…" : "确认重置"}
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="home-profile-init-reset-button"
                onClick={() => setResetConfirmOpen(true)}
                disabled={profileLoading || submitting || resetting}
              >
                重置画像
              </button>
            )}
          </div>

          <div className="home-profile-init-actions">
            <button
              type="button"
              className="home-profile-init-secondary"
              onClick={handleSkip}
              disabled={profileLoading || submitting || resetting}
            >暂时跳过
            </button>
            <button type="submit" className="home-profile-init-primary" disabled={profileLoading || submitting || resetting || overwriteConfirmOpen}>
              {submitting ? "正在保存…" : existingProfile ? "保存学习画像" : "完成学习画像"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

export default GlobalProfileInitPage;
