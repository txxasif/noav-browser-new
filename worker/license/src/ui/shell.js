/** Assembles the full admin page from head + dashboard + billing + modal + scripts. */
import { headHtml } from './head.js';
import { dashboardHtml } from './licenses.js';
import { moneyHtml } from './money.js';
import { billingHtml } from './billing.js';
import { modalHtml } from './modal.js';
import { licenseScript } from './client-licenses.js';
import { billingScript } from './client-billing.js';

export function adminHtml() {
  return (
    headHtml() +
    dashboardHtml() +
    moneyHtml() +
    billingHtml() +
    modalHtml() +
    '\n  <script>' +
    licenseScript() +
    '\n  </script>' +
    '\n  <script>' +
    billingScript() +
    '\n  </script>' +
    '\n</body>\n</html>'
  );
}
