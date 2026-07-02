function PreviewSection() {
return (
    <section className="preview-section">
    <div className="preview-text">
        <span className="section-tag">为什么选择这个平台</span>
        <h2>工具简单，进度清晰，结果更好。</h2>
        <p>面向现代课堂设计，支持结构化内容、便捷沟通和灵活学习路径。
        </p>

        <ul>
        <li>互动课程和测验</li>
        <li>教师控制台和班级管理</li>
        <li>跨设备友好的学习界面</li>
        </ul>
    </div>

    <div className="preview-visual">
        <div className="visual-card main-card">
        <img
            src="https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=900&q=80"
            alt="课堂"
        />
        </div>

        <div className="floating-card card-one">
        <strong>92%</strong>
        <span>学生参与度</span>
        </div>

        <div className="floating-card card-two">
        <strong>24/7</strong>
        <span>学习入口</span>
        </div>
    </div>
    </section>
);
}

export default PreviewSection;