import { Navigate, Route, Routes } from "react-router-dom";

import MarketingHomePage from "../components/home/HomePage";
import { clearStoredSession } from "../services/api";
import AiDemo from "../pages/AiDemo/AiDemo";
import ChangePassword from "../pages/ChangePassword/ChangePassword";
import CourseJoinPage from "../pages/Course/CourseJoinPage";
import CourseLayout from "../pages/Course/CourseLayout";
import CourseManagementLayout from "../pages/Course/CourseManagementLayout";
import CourseManagementModuleCreatePage from "../pages/Course/CourseManagementModuleCreatePage";
import CourseManagementModuleDetailPage from "../pages/Course/CourseManagementModuleDetailPage";
import CourseManagementMaterialsPage from "../pages/Course/CourseManagementMaterialsPage";
import CourseManagementModulesPage from "../pages/Course/CourseManagementModulesPage";
import CourseManagementOverviewPage from "../pages/Course/CourseManagementOverviewPage";
import CourseManagementPublishingPage from "../pages/Course/CourseManagementPublishingPage";
import CourseManagementQuizPage from "../pages/Course/CourseManagementQuizPage";
import CourseManagementShortAnswerPage from "../pages/Course/CourseManagementShortAnswerPage";
import CourseManagementUserEnrolmentsPage from "../pages/Course/CourseManagementUserEnrolmentsPage";
import CourseMaterialPage from "../pages/Course/CourseMaterialPage";
import CourseModulePage from "../pages/Course/CourseModulePage";
import CourseQuizPage from "../pages/Course/CourseQuizPage";
import CourseShortAnswerPage from "../pages/Course/CourseShortAnswerPage";
import CourseForumPage from "../pages/Course/CourseForumPage";
import CourseOverviewPage from "../pages/Course/CourseOverviewPage";
import ForgotPassword from "../pages/ForgotPassword/ForgotPassword";
import GlobalProfileInitPage from "../pages/Home/GlobalProfileInitPage";
import HomeAiPage from "../pages/Home/HomeAiPage";
import HomeOverviewPage from "../pages/Home/HomeOverviewPage";
import HomePage from "../pages/Home/HomePage";
import HomeSectionPage from "../pages/Home/HomeSectionPage";
import StudyPlannerPage from "../pages/Home/StudyPlannerPage";
import Login from "../pages/Login/Login";
import EducatorInviteRegister from "../pages/Register/EducatorInviteRegister";
import Register from "../pages/Register/Register";
import ResetPassword from "../pages/ResetPassword/ResetPassword";
import Terms from "../pages/Terms/Terms";
import VerifyEmail from "../pages/VerifyEmail/VerifyEmail";

function hasUsableAccessToken() {
    const token = localStorage.getItem("accessToken");
    if (!token) {
        return false;
    }

    const [, payload] = token.split(".");
    if (!payload) {
        return true;
    }

    try {
        const normalizedPayload = payload.replace(/-/g, "+").replace(/_/g, "/");
        const decodedPayload = JSON.parse(window.atob(normalizedPayload)) as { exp?: unknown };
        if (typeof decodedPayload.exp !== "number") {
            return true;
        }
        return decodedPayload.exp * 1000 > Date.now();
    } catch {
        return false;
    }
}

function RootRoute() {
    if (hasUsableAccessToken()) {
        return <Navigate to="/home" replace />;
    }

    clearStoredSession();
    return <MarketingHomePage />;
}

function NotFoundRedirect() {
    const token = localStorage.getItem("accessToken");
    return <Navigate to={token ? "/home" : "/"} replace />;
}

function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<RootRoute />} />
            <Route path="/home" element={<HomePage />}>
                <Route index element={<HomeOverviewPage />} />
                <Route path="course-center" element={<HomeSectionPage sectionId="course-center" />} />
                <Route path="my-courses" element={<HomeSectionPage sectionId="my-courses" />} />
                <Route path="managed-courses" element={<HomeSectionPage sectionId="managed-courses" />} />
                <Route path="communication" element={<HomeSectionPage sectionId="communication" />} />
                <Route path="progress" element={<HomeSectionPage sectionId="progress" />} />
                <Route path="study-planner" element={<StudyPlannerPage />} />
                <Route path="ai" element={<HomeAiPage />} />
                <Route path="ai/profile-init" element={<GlobalProfileInitPage />} />
                <Route path="analytics" element={<HomeSectionPage sectionId="analytics" />} />
                <Route path="course-management" element={<HomeSectionPage sectionId="course-management" />} />
                <Route path="user-management" element={<HomeSectionPage sectionId="user-management" />} />
                <Route path="educator-requests" element={<HomeSectionPage sectionId="educator-requests" />} />
                <Route path="communication-management" element={<HomeSectionPage sectionId="communication-management" />} />
            </Route>
            <Route path="/ai-demo" element={<AiDemo />} />
            <Route path="/ai-demo/:sessionUuid" element={<AiDemo />} />
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
                <Route path="modules/:moduleUuid/short-answer" element={<CourseShortAnswerPage />} />
            </Route>
            <Route path="/course/:courseUuid/management" element={<CourseManagementLayout />}>
                <Route index element={<CourseManagementOverviewPage />} />
                <Route path="modules" element={<CourseManagementModulesPage />} />
                <Route path="modules/new" element={<CourseManagementModuleCreatePage />} />
                <Route path="modules/:moduleUuid" element={<CourseManagementModuleDetailPage />} />
                <Route path="modules/:moduleUuid/quiz" element={<CourseManagementQuizPage />} />
                <Route path="modules/:moduleUuid/short-answer" element={<CourseManagementShortAnswerPage />} />
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
    );
}

export default AppRoutes;
