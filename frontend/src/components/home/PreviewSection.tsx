function PreviewSection() {
return (
    <section className="preview-section">
    <div className="preview-text">
        <span className="section-tag">Why choose us</span>
        <h2>Simple tools. Clear progress. Better outcomes.</h2>
        <p>
        Designed for modern classrooms with structured content, easy
        communication, and flexible learning paths.
        </p>

        <ul>
        <li>Interactive lessons and quizzes</li>
        <li>Teacher dashboard and class management</li>
        <li>learner-friendly interface across devices</li>
        </ul>
    </div>

    <div className="preview-visual">
        <div className="visual-card main-card">
        <img
            src="https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=900&q=80"
            alt="classroom"
        />
        </div>

        <div className="floating-card card-one">
        <strong>92%</strong>
        <span>learner engagement</span>
        </div>

        <div className="floating-card card-two">
        <strong>24/7</strong>
        <span>Learning access</span>
        </div>
    </div>
    </section>
);
}

export default PreviewSection;