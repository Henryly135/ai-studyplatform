import { useNavigate } from "react-router-dom";

function RoleSection() {
    const navigate = useNavigate();

    return (
        <section className="role-section">
            <div className="role-card featured">
                <h3>学生</h3>
                <p>加入课程、完成学习并追踪进度。</p>
                <button
                    type="button"
                    onClick={() => {
                        navigate("/register/learner");
                    }}
                >注册学生账号
                </button>
            </div>

            <div className="role-card">
                <h3>教师</h3>
                <p>创建课程、安排活动并支持学生。</p>
                <button
                    type="button"
                    onClick={() => {
                        navigate("/register/educator");
                    }}
                >注册教师账号
                </button>
            </div>
        </section>
    );
}

export default RoleSection;
