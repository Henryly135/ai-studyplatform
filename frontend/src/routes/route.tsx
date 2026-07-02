import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { clearStoredSession } from "../services/api";
import { isUsableAccessToken } from "../utils/accessToken";

const MarketingHomePage = lazy(() => import("../components/home/HomePage"));
const ChangePassword = lazy(() => import("../pages/ChangePassword/ChangePassword"));
const CourseJoinPage = lazy(() => import("../pages/Course/CourseJoinPage"));
const CourseLayout = lazy(() => import("../pages/Course/CourseLayout"));
const CourseManagementLayout = lazy(() => import("../pages/Course/CourseManagementLayout"));
const CourseManagementModuleCreatePage = lazy(() => import("../pages/Course/CourseManagementModuleCreatePage"));
const CourseManagementModuleDetailPage = lazy(() => import("../pages/Course/CourseManagementModuleDetailPage"));
const CourseManagementMaterialsPage = lazy(() => import("../pages/Course/CourseManagementMaterialsPage"));
const CourseManagementModulesPage = lazy(() => import("../pages/Course/CourseManagementModulesPage"));
const CourseManagementOverviewPage = lazy(() => import("../pages/Course/CourseManagementOverviewPage"));
const CourseManagementPublishingPage = lazy(() => import("../pages/Course/CourseManagementPublishingPage"));
const CourseManagementQuizPage = lazy(() => import("../pages/Course/CourseManagementQuizPage"));
const CourseManagementUserEnrolmentsPage = lazy(() => import("../pages/Course/CourseManagementUserEnrolmentsPage"));
const CourseMaterialPage = lazy(() => import("../pages/Course/CourseMaterialPage"));
const CourseModulePage = lazy(() => import("../pages/Course/CourseModulePage"));
const CourseQuizPage = lazy(() => import("../pages/Course/CourseQuizPage"));
const CourseForumPage = lazy(() => import("../pages/Course/CourseForumPage"));
const CourseOverviewPage = lazy(() => import("../pages/Course/CourseOverviewPage"));
const ForgotPassword = lazy(() => import("../pages/ForgotPassword/ForgotPassword"));
const GlobalProfileInitPage = lazy(() => import("../pages/Home/GlobalProfileInitPage"));
const HomeAiPage = lazy(() => import("../pages/Home/HomeAiPage"));
const HomeOverviewPage = lazy(() => import("../pages/Home/HomeOverviewPage"));
const HomePage = lazy(() => import("../pages/Home/HomePage"));
const HomeSectionPage = lazy(() => import("../pages/Home/HomeSectionPage"));
const Login = lazy(() => import("../pages/Login/Login"));
const EducatorInviteRegister = lazy(() => import("../pages/Register/EducatorInviteRegister"));
const Register = lazy(() => import("../pages/Register/Register"));
const ResetPassword = lazy(() => import("../pages/ResetPassword/ResetPassword"));
const Terms = lazy(() => import("../pages/Terms/Terms"));
const VerifyEmail = lazy(() => import("../pages/VerifyEmail/VerifyEmail"));

function hasUsableStoredAccessToken() {
    return isUsableAccessToken(localStorage.getItem("accessToken"));
}

function RootRoute() {
    if (hasUsableStoredAccessToken()) {
        return <Navigate to="/home" replace />;
    }

    clearStoredSession();
    return <MarketingHomePage />;
}

function NotFoundRedirect() {
    const hasToken = hasUsableStoredAccessToken();
    if (!hasToken) {
        clearStoredSession();
    }

    return <Navigate to={hasToken ? "/home" : "/"} replace />;
}

function AppRoutes() {
    return (
        <Suspense fallback={<div className="app-route-loading">Loading...</div>}>
            <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/home" element={<HomePage />}>
                    <Route index element={<HomeOverviewPage />} />
                    <Route path="course-center" element={<HomeSectionPage sectionId="course-center" />} />
                    <Route path="my-courses" element={<HomeSectionPage sectionId="my-courses" />} />
                    <Route path="managed-courses" element={<HomeSectionPage sectionId="managed-courses" />} />
                    <Route path="communication" element={<HomeSectionPage sectionId="communication" />} />
                    <Route path="progress" element={<HomeSectionPage sectionId="progress" />} />
                    <Route path="ai" element={<HomeAiPage />} />
                    <Route path="ai/profile-init" element={<GlobalProfileInitPage />} />
                    <Route path="analytics" element={<HomeSectionPage sectionId="analytics" />} />
                    <Route path="course-management" element={<HomeSectionPage sectionId="course-management" />} />
                    <Route path="user-management" element={<HomeSectionPage sectionId="user-management" />} />
                </Route>
                <Route path="/ai-demo" element={<Navigate to="/home/ai" replace />} />
                <Route path="/ai-demo/:sessionUuid" element={<Navigate to="/home/ai" replace />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register/:role" element={<Register />} />
                <Route path="/register/educator-invite" element={<EducatorInviteRegister />} />
                <Route path="/courses/join" element={<CourseJoinPage />} />
                <Route path="/course/:courseUuid" element={<CourseLayout />}>
                    <Route index element={<CourseOverviewPage />} />
                    <Route path="forum" element={<CourseForumPage />} />
                    <Route path="forum/:postUuid" element={<CourseForumPage />} />
                    <Route path="modules/:moduleUuid" element={<CourseModulePage />} />
                    <Route path="modules/:moduleUuid/materials/:materialUuid" element={<CourseMaterialPage />} />
                    <Route path="modules/:moduleUuid/quiz" element={<CourseQuizPage />} />
                </Route>
                <Route path="/course/:courseUuid/management" element={<CourseManagementLayout />}>
                    <Route index element={<CourseManagementOverviewPage />} />
                    <Route path="modules" element={<CourseManagementModulesPage />} />
                    <Route path="modules/new" element={<CourseManagementModuleCreatePage />} />
                    <Route path="modules/:moduleUuid" element={<CourseManagementModuleDetailPage />} />
                    <Route path="modules/:moduleUuid/quiz" element={<CourseManagementQuizPage />} />
                    <Route path="enrolments" element={<CourseManagementUserEnrolmentsPage />} />
                    <Route path="materials" element={<CourseManagementMaterialsPage />} />
                    <Route path="publishing" element={<CourseManagementPublishingPage />} />
                </Route>
                <Route path="/verify-email" element={<VerifyEmail />} />
                <Route path="/terms" element={<Terms />} />
                <Route path="/change-password" element={<ChangePassword />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="*" element={<NotFoundRedirect />} />
            </Routes>
        </Suspense>
    );
}

export default AppRoutes;
