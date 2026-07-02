import { Link } from "react-router-dom";
import "./Terms.css";

function Terms() {
  return (
    <div className="terms-page">
      <div className="terms-container">
        <div className="terms-header">
          <h1>服务条款</h1>
          <p className="terms-effective">生效日期：2026 年 3 月</p>
        </div>

        <section>
          <h2>1. 关于学习平台</h2>
          <p>
            本平台是面向教学场景的在线学习系统，连接学生、教师和管理员。注册账号即表示你同意本服务条款；
            如果不同意，请不要继续使用本平台。
          </p>
        </section>

        <section>
          <h2>2. 用户账号</h2>
          <ul>
            <li>你需要提供有效邮箱，并在访问平台前完成邮箱验证。</li>
            <li>你需要妥善保管账号凭据。</li>
            <li>不得共享自己的账号，也不得使用他人的账号。</li>
            <li>
              平台包含三类账号：<strong>学生</strong>、<strong>教师</strong>和
              <strong>管理员</strong>，不同账号拥有不同权限。
            </li>
          </ul>
        </section>

        <section>
          <h2>3. 用户行为</h2>
          <p>所有用户承诺不会：</p>
          <ul>
            <li>上传或分享违法、有害、辱骂性或歧视性内容。</li>
            <li>侵犯他人的知识产权。</li>
            <li>将平台用于教育活动以外的目的。</li>
            <li>试图干扰、攻击平台，或未经授权访问平台及其他用户账号。</li>
            <li>冒充任何个人或组织。</li>
          </ul>
        </section>

        <section>
          <h2>4. 内容</h2>
          <ul>
            <li>
              教师可以上传视频、文档和文本等课程资料。上传者保留内容所有权，同时授权平台向已加入课程的用户托管和展示这些内容。
            </li>
            <li>
              上传者需要对自己上传的内容负责。平台不会预先审核所有内容，但保留移除违反本条款内容的权利。
            </li>
            <li>
              学生只能访问自己已加入课程中的内容，不得在平台外重新分发课程资料。
            </li>
          </ul>
        </section>

        <section>
          <h2>5. 隐私与数据</h2>
          <ul>
            <li>平台会收集姓名、邮箱和账号活动信息，用于维持平台运行。</li>
            <li>平台不会向第三方出售你的数据。</li>
            <li>
              平台仅使用邮箱发送账号验证、密码重置和平台相关通知。
            </li>
            <li>你可以联系管理员请求删除账号及相关数据。</li>
          </ul>
        </section>

        <section>
          <h2>6. 账号终止</h2>
          <p>
            对于违反本条款、存在不当行为或长期不活跃的账号，平台保留暂停或终止账号的权利。管理员可以管理其机构内的用户账号。
          </p>
        </section>

        <section>
          <h2>7. 免责声明</h2>
          <p>
            本平台按现状提供，用于教育目的。平台不保证服务持续不中断，也不对数据或访问损失承担责任。
            当前平台免费提供，不产生付款义务。
          </p>
        </section>

        <section>
          <h2>8. 条款变更</h2>
          <p>
            平台可能不时更新本条款。更新发布后继续使用平台，即表示接受更新后的条款。
          </p>
        </section>

        <section>
          <h2>9. 联系方式</h2>
          <p>
            如对本条款有疑问，请联系所在机构的管理员。
          </p>
        </section>

        <div className="terms-back">
          <Link to="/register" className="text-link">返回注册</Link>
        </div>
      </div>
    </div>
  );
}

export default Terms;
