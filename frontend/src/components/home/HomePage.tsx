import Navbar from "../layouts/navbar";
import HeroSection from "./HeroSection";
import RoleSection from "./RoleSection";
import PreviewSection from "./PreviewSection";

function HomePage() {
return (
    <div className="page">
    <Navbar />

    <main className="hero">
        <HeroSection />
        <RoleSection />
        <PreviewSection />
    </main>
    </div>
);
}

export default HomePage;