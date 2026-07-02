import { useEffect, useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { LuCircleCheckBig } from "react-icons/lu";

import { initializeGlobalProfile } from "../../services/profile";
import type { GlobalProfileInitRequest } from "../../types/profile";
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

const INITIAL_FORM: ProfileFieldState = {
  supportRole: { selectedOption: "", otherValue: "" },
  helpStyle: { selectedOption: "", otherValue: "" },
  learningFocus: { selectedOption: "", otherValue: "" },
  responseTone: { selectedOption: "", otherValue: "" },
};

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
  const [form, setForm] = useState<ProfileFieldState>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!successMessage) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      const target = getRedirectTarget();
      localStorage.removeItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY);
      navigate(target, { replace: true });
    }, SUCCESS_TOAST_DISPLAY_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [navigate, successMessage]);

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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (Object.values(payloadPreview).some((value) => value.length === 0)) {
      setErrorMessage("请为每个属性选择一个选项。如果选择其他，请补充简短说明。");
      return;
    }

    try {
      setSubmitting(true);
      await initializeGlobalProfile(payloadPreview);
      setSuccessMessage("学习画像初始化成功。");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to initialize your profile."
      );
      setSubmitting(false);
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
          <h1>初始化学习画像</h1>
          <p>
            一次性设置偏好，让智能助手在之后的学习活动中更稳定地支持你。
          </p>
        </div>

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
                        disabled={submitting}
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
                      disabled={submitting}
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

          <div className="home-profile-init-actions">
            <button
              type="button"
              className="home-profile-init-secondary"
              onClick={handleSkip}
              disabled={submitting}
            >暂时跳过
            </button>
            <button type="submit" className="home-profile-init-primary" disabled={submitting}>
              {submitting ? "Saving profile..." : "Complete learning profile"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

export default GlobalProfileInitPage;
