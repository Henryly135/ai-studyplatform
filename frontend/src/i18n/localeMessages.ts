export type AppLocale = "en" | "zh";

type UploadText = {
  materialFileLabel: string;
  coverImageLabel: string;
  chooseFile: string;
  changeFile: string;
  noFileSelected: string;
};

export type LocaleMessages = {
  upload: UploadText;
};

export const LOCALE_STORAGE_KEY = "app.locale";

export const localeMessages: Record<AppLocale, LocaleMessages> = {
  en: {
    upload: {
      materialFileLabel: "Choose file",
      coverImageLabel: "Cover image",
      chooseFile: "Choose file",
      changeFile: "Change file",
      noFileSelected: "No file selected",
    },
  },
  zh: {
    upload: {
      materialFileLabel: "选择文件",
      coverImageLabel: "封面图片",
      chooseFile: "选择文件",
      changeFile: "更换文件",
      noFileSelected: "未选择文件",
    },
  },
};
