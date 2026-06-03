// FILE: frontend-admin/src/components/BrandMark.tsx
// VERSION: 1.0.0
// ROLE: UI_COMPONENT
// MAP_MODE: EXPORTS
// START_MODULE_CONTRACT
//   PURPOSE: Reusable visible KrotPN logo mark for admin login and protected admin shell surfaces
//   SCOPE: Size-bounded PNG logo rendering, optional text lockup, Phase-63 admin visibility markers, and email/BIMI boundary-safe asset use
//   DEPENDS: M-010 (frontend-admin), M-069 (brand-assets-favicon-email-logo), M-072 (premium-art-direction-system), M-080 (visible-brand-logo-integration)
//   LINKS: M-080, V-M-080, docs/plans/Phase-63.xml
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   BRAND_MARK_SRC - Primary compact visible logo asset selected from prepared 96x96 PNG source
//   BRAND_MARK_RETINA_SRC - Existing frontend email body logo path retained as high-DPI reference without changing Resend/BIMI semantics
//   BrandMark - Reusable compact admin logo lockup component
//   default - React component (default export)
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added Phase-63 visible KrotPN admin logo component with bounded asset selection and admin shell markers.
// END_CHANGE_SUMMARY
//
// START_BLOCK_BRAND_MARK
import type { HTMLAttributes } from 'react'

const BRAND_MARK_SRC = '/brand/krotpn-mark-96.png'
const BRAND_MARK_RETINA_SRC = '/brand/krotpn-mark-96.png'

type BrandMarkSize = 'sm' | 'md' | 'lg'

type BrandMarkProps = HTMLAttributes<HTMLSpanElement> & {
  label?: string
  marker?: string
  showText?: boolean
  size?: BrandMarkSize
  textClassName?: string
}

const sizeClassByName: Record<BrandMarkSize, string> = {
  sm: 'phase63-brand-mark-sm',
  md: 'phase63-brand-mark-md',
  lg: 'phase63-brand-mark-lg',
}

export default function BrandMark({
  className = '',
  label = 'KrotPN',
  marker = '[VisibleBrandLogo][phase63][ADMIN_SHELL_LOGO_SAFE]',
  showText = false,
  size = 'md',
  textClassName = '',
  ...rest
}: BrandMarkProps) {
  const ariaLabel = rest['aria-label'] || label

  return (
    <span
      {...rest}
      aria-label={ariaLabel}
      className={['phase63-brand-lockup', showText ? 'phase63-brand-lockup-with-text' : '', className].filter(Boolean).join(' ')}
      data-phase63-logo={marker}
    >
      <span className={['phase63-brand-mark', sizeClassByName[size]].join(' ')} aria-hidden="true">
        <img
          src={BRAND_MARK_SRC}
          srcSet={`${BRAND_MARK_SRC} 1x, ${BRAND_MARK_RETINA_SRC} 2x`}
          alt=""
          className="phase63-brand-image"
          width="96"
          height="96"
          draggable={false}
        />
      </span>
      {showText ? <span className={['phase63-brand-text', textClassName].filter(Boolean).join(' ')}>{label}</span> : null}
    </span>
  )
}
// END_BLOCK_BRAND_MARK
