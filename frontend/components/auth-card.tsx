import Link from "next/link";
export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link className="brand" href="/login">
          <span className="brand-symbol">M</span>
          <span>
            Maintain<span className="brand-gold">IQ</span>
          </span>
        </Link>
        <div>
          <div className="small-kicker">
            KNOW YOUR EQUIPMENT. KEEP YOUR HISTORY.
          </div>
          <h1>
            Better maintenance
            <br />
            starts with a<br />
            <em>clearer picture.</em>
          </h1>
          <p>
            A focused workspace for your assets, your sites,
            <br />
            and the people who keep them running.
          </p>
        </div>
        <p className="auth-footnote">
          Foundation release · Synthetic demonstration available
          <br />
          No operational safety or predictive-maintenance claims.
        </p>
      </section>
      <section className="auth-form-wrap">
        <div className="auth-card">
          <div className="eyebrow">WELCOME TO MAINTAINIQ</div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
          {children}
        </div>
      </section>
    </main>
  );
}
