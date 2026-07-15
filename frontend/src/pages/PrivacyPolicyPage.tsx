import { Link } from "react-router-dom";
import { ClubLogo } from "../components/ClubLogo";
import { CLUB_NAME } from "../lib/clubBrand";
import {
  PRIVACY_CONTACT_EMAIL,
  PRIVACY_CONTROLLER_DETAILS,
  PRIVACY_CONTROLLER_NAME,
  PRIVACY_POLICY_EFFECTIVE,
  PRIVACY_POLICY_VERSION,
} from "../lib/privacy";

export function PrivacyPolicyPage() {
  return (
    <div className="boot-screen app-shell">
      <article className="auth-card privacy-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <p className="page-header__eyebrow">GDPR</p>
          <h1 className="trainer-picker__title">Zásady ochrany osobních údajů</h1>
          <p className="trainer-picker__sub">
            {CLUB_NAME} · verze {PRIVACY_POLICY_VERSION} · účinnost od {PRIVACY_POLICY_EFFECTIVE}
          </p>
        </header>

        <div className="privacy-body">
          <section>
            <h2>1. Správce údajů</h2>
            <p>
              Správcem osobních údajů je <strong>{PRIVACY_CONTROLLER_NAME}</strong>.{" "}
              {PRIVACY_CONTROLLER_DETAILS}
            </p>
            <p>
              Kontakt pro žádosti ohledně osobních údajů:{" "}
              {PRIVACY_CONTACT_EMAIL ? (
                <a href={`mailto:${PRIVACY_CONTACT_EMAIL}`}>{PRIVACY_CONTACT_EMAIL}</a>
              ) : (
                <em>e-mail doplní klub před ostrým provozem</em>
              )}
            </p>
          </section>

          <section>
            <h2>2. Co aplikace dělá</h2>
            <p>
              Webová aplikace slouží k evidenci žáků a rodičů, docházce na tréninky, komunikaci trenérů
              s rodiči, oznámením, událostem a schvalování online přihlášek do klubu.
            </p>
          </section>

          <section>
            <h2>3. Jaké údaje zpracováváme</h2>
            <h3>Rodič / zákonný zástupce</h3>
            <ul>
              <li>jméno a příjmení</li>
              <li>e-mail a telefon</li>
              <li>uživatelské jméno a heslo (účet)</li>
              <li>obsah zpráv v chatu, odpovědi na akce (RSVP) a oznámení</li>
            </ul>
            <h3>Dítě / žák</h3>
            <ul>
              <li>jméno a příjmení</li>
              <li>datum narození a věková kategorie</li>
              <li>rodné číslo</li>
              <li>zdravotní pojišťovna</li>
              <li>pobočka a tréninková skupina</li>
              <li>docházka a účast na akcích</li>
            </ul>
            <h3>Trenér</h3>
            <ul>
              <li>jméno, příjmení a přiřazené pobočky</li>
              <li>technické údaje přihlášení (PIN / token)</li>
            </ul>
            <h3>Technické údaje</h3>
            <ul>
              <li>přihlašovací tokeny v prohlížeči (sessionStorage)</li>
              <li>provozní logy v nezbytném rozsahu</li>
              <li>soubory nahrané u událostí, pokud je funkce použita</li>
            </ul>
          </section>

          <section>
            <h2>4. Účely a právní základy</h2>
            <ul>
              <li>
                <strong>Evidence členů / žáků a registrace</strong> — plnění smlouvy / oprávněný zájem
                klubu a souhlas při online přihlášce.
              </li>
              <li>
                <strong>Rodné číslo</strong> — pouze v rozsahu nutném pro identifikaci žáka v klubu
                (právní základ doplní klub podle své praxe: smlouva, právní povinnost nebo souhlas).
              </li>
              <li>
                <strong>Zdravotní pojišťovna</strong> — oprávněný zájem / souhlas (organizace provozu a
                akcí; nejde o zdravotní dokumentaci).
              </li>
              <li>
                <strong>Docházka, skupiny, pobočky</strong> — smlouva / oprávněný zájem.
              </li>
              <li>
                <strong>Chat, oznámení a e-maily s přihlašovacími údaji</strong> — smlouva / oprávněný
                zájem.
              </li>
              <li>
                <strong>Bezpečnost účtů</strong> — oprávněný zájem.
              </li>
            </ul>
            <p>
              Údaje dětí zpracováváme prostřednictvím zákonného zástupce. Online přihlášku podává rodič.
            </p>
          </section>

          <section>
            <h2>5. Kdo má k údajům přístup</h2>
            <ul>
              <li>administrátor klubu — správa účtů, schvalování registrací, exporty</li>
              <li>trenéři — žáci, docházka a komunikace v rozsahu potřebném pro provoz</li>
              <li>rodič — vlastní profil a své děti</li>
            </ul>
            <p>
              Údaje mohou zpracovávat i dodavatelé služeb (hosting aplikace a databáze, e-mailová
              služba) v EU, typicky hosting v regionu Frankfurt. S těmito zpracovateli uzavírá klub
              smlouvy o zpracování osobních údajů, pokud je to vyžadováno.
            </p>
          </section>

          <section>
            <h2>6. Doba uchování</h2>
            <ul>
              <li>aktivní člen / žák a rodič — po dobu členství a přiměřenou dobu po ukončení</li>
              <li>docházka — po dobu členství a následnou archivační dobu dle praxe klubu</li>
              <li>chat a oznámení — po dobu potřebnou pro provoz komunikace, nejdéle do smazání účtu</li>
              <li>zamítnutá nebo nevyřízená registrace — přiměřenou dobu (řádově měsíce), poté smazání</li>
              <li>technické logy — krátkodobě (řádově desítky dní)</li>
            </ul>
            <p>Po uplynutí doby údaje smažeme nebo anonymizujeme.</p>
          </section>

          <section>
            <h2>7. Vaše práva</h2>
            <p>Máte právo požadovat:</p>
            <ul>
              <li>přístup k osobním údajům</li>
              <li>opravu (část údajů můžete upravit přímo v aplikaci)</li>
              <li>výmaz</li>
              <li>omezení zpracování</li>
              <li>přenositelnost</li>
              <li>námitku proti zpracování na základě oprávněného zájmu</li>
              <li>podání stížnosti u Úřadu pro ochranu osobních údajů (www.uoou.cz)</li>
            </ul>
            <p>
              Žádosti posílejte na kontakt výše. Odpovíme zpravidla do 1 měsíce.
            </p>
          </section>

          <section>
            <h2>8. Cookies a podobné technologie</h2>
            <p>
              Aplikace používá nezbytné přihlašovací tokeny v <code>sessionStorage</code> kvůli chodu
              služby. Marketingové cookies ani analytiku třetích stran aktuálně nepoužíváme. Pokud je
              klub v budoucnu přidá, doplní informace a případný souhlas.
            </p>
          </section>

          <section>
            <h2>9. Zabezpečení</h2>
            <p>
              Hesla a PIN ukládáme v hashované podobě. Přístup k údajům je vázán na přihlášení.
              Komunikace probíhá přes HTTPS. Hosting aplikace je směřován do EU.
            </p>
          </section>

          <section>
            <h2>10. Změny zásad</h2>
            <p>
              Změny zveřejníme na této stránce. U podstatných změn budeme informovat také e-mailem nebo
              oznámením v aplikaci.
            </p>
          </section>
        </div>

        <div className="confirm-card__actions">
          <Link to="/" className="btn btn--ghost">
            Zpět na úvod
          </Link>
          <Link to="/register" className="btn btn--primary">
            K registraci
          </Link>
        </div>
      </article>
    </div>
  );
}
