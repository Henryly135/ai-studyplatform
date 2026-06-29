import { useNavigate } from "react-router-dom";

function RoleSection() {
    const navigate = useNavigate();

    return (
        <section className="role-section">
            <div className="role-card featured">
                <h3>Learner</h3>
                <p>Join classes, complete lessons, and track your progress.</p>
                <button
                    type="button"
                    onClick={() => {
                        console.log("learner clicked");
                        navigate("/register/learner");
                    }}
                >
                    Sign up as Learner
                </button>
            </div>

            <div className="role-card">
                <h3>Educator</h3>
                <p>Create courses, assign activities, and support learners.</p>
                <button
                    type="button"
                    onClick={() => {
                        console.log("educator clicked");
                        navigate("/register/educator");
                    }}
                >
                    Sign up as Educator
                </button>
            </div>
        </section>
    );
}

export default RoleSection;