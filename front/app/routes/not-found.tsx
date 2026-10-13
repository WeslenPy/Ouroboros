import { useTranslation } from "react-i18next"

import { ErrorPage } from "~/components/custom/error-page"

export default function NotFound() {
  const { t } = useTranslation()
  return <ErrorPage statusCode={404} title={t("errors.404")} message={t("errors.notFound")} />
}
