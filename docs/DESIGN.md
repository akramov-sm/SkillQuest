# SkillQuest — UI/UX Design System

**Концепция: Premium Dark Futuristic.** Почти чёрный графит, электрический фиолетовый и синий акценты, мягкие свечения, тонкие границы. Ориентиры: Linear (чёткость, плотность), Notion (читаемость, спокойствие), RPG-платформы (прогресс, награды). Декор — только там, где он несёт смысл (прогресс, награды).

## 1. Цвета (CSS custom properties)
| Токен | Значение | Назначение |
|---|---|---|
| `--bg` | `#07070b` | фон приложения |
| `--bg-elev` | `#0d0d14` | сайдбар, шапка |
| `--surface` | `#12121b` | карточки |
| `--surface-2` | `#181824` | hover / вложенные блоки |
| `--border` | `rgba(255,255,255,.07)` | границы |
| `--border-strong` | `rgba(255,255,255,.14)` | hover-границы |
| `--text` | `#ececf3` | основной текст |
| `--text-2` | `#a0a0b8` | вторичный |
| `--text-3` | `#6c6c85` | подсказки (контраст ≥ 4.5:1 на `--surface` только для крупного/декор.) |
| `--violet` | `#8b5cf6` | основной акцент |
| `--blue` | `#3b82f6` | вторичный акцент |
| `--grad` | `linear-gradient(135deg,#8b5cf6,#3b82f6)` | кнопки, прогресс |
| `--success` / `--warning` / `--danger` | `#34d399` / `#fbbf24` / `#f87171` | статусы |

Категории: Programming `#8b5cf6`, AI `#3b82f6`, English `#22d3ee`, Fitness `#34d399`, Finance `#fbbf24`, Personal Dev `#f472b6`.
Сложность: Easy — зелёный, Medium — синий, Hard — оранжевый, Epic — фиолетовый/розовый градиент.

## 2. Типографика
Шрифт: `Inter, ui-sans-serif, -apple-system, "SF Pro Text", "Segoe UI", sans-serif` (локальный стек, без CDN). Числа — `font-variant-numeric: tabular-nums`.
| Роль | Размер / вес |
|---|---|
| Display (уровень) | 48 / 700, letter-spacing −0.03em |
| H1 страницы | 24 / 650 |
| H2 карточки | 15 / 600 |
| Body | 14 / 450, line-height 1.5 |
| Caption/labels | 12 / 500, uppercase опционально, `--text-3` |

## 3. Сетка, радиусы, отступы
Шкала 4px (4, 8, 12, 16, 20, 24, 32). Радиусы: 8 (контролы), 14 (карточки), 999 (чипы). Контент max-width 1200px. Dashboard — 12-колоночная сетка с `gap: 16px`.

## 4. Эффекты
- Карточка: `surface` + 1px граница + лёгкий верхний градиент-«блик» (`inset 0 1px 0 rgba(255,255,255,.04)`).
- Свечение: `box-shadow: 0 0 0 1px …, 0 8px 32px -8px rgba(139,92,246,.45)` — для primary-кнопок, XP-бара, активных элементов.
- Ambient-фон: два размытых радиальных градиента (фиолетовый сверху-слева, синий снизу-справа) с низкой непрозрачностью.
- Анимации: 150–250ms `cubic-bezier(.2,.8,.2,1)`; заполнение прогресс-баров, появление карточек (fade+translateY 6px), pop для галочки миссии, shimmer для skeleton. `prefers-reduced-motion` отключает всё кроме смены цвета.

## 5. Компоненты
Sidebar (логотип, навигация, мини-карточка уровня) · Topbar (заголовок, «New mission») · Card · Stat tile · Progress bar (градиент, glow) · Ring/Donut · Bar chart с tooltip · Chip/Badge (категория, сложность, статус) · Button (primary/ghost/danger, sm/md) · Input/Select/Textarea/Segmented · Modal (+confirm) · Toast (success/error/achievement/level-up) · Mission row (чекбокс, мета, действия) · Skill card (тиры-ноды) · Achievement card (locked/unlocked, прогресс) · Empty state · Skeleton · Error state.

## 6. Состояния
Hover (поднятие границы/фона), focus-visible (2px фиолетовое кольцо), active (scale .98), disabled (opacity .5), loading (spinner на кнопке/skeleton), error (красная рамка + текст под полем), empty (иконка + пояснение + CTA).

## 7. Адаптивность
| Ширина | Поведение |
|---|---|
| ≥1100 | Сайдбар 240px, Dashboard 12 колонок |
| 760–1099 | Сайдбар сворачивается до иконок (72px), 2 колонки |
| <760 | Сайдбар скрыт → нижняя навигация (6 иконок), 1 колонка, модалки как bottom-sheet, кнопки ≥44px |

## 8. Доступность
Семантические теги (`nav`, `main`, `button`), `aria-label` у иконок-кнопок, `role="dialog"` + `aria-modal`, управление фокусом и закрытие по Esc, тосты в `aria-live="polite"`, цвет не единственный носитель смысла (иконки/текст).

## 9. Тон интерфейса
Короткие английские подписи, «игровая» лексика в меру: Missions, XP, Level up, Streak. Пустые состояния дружелюбные и с призывом к действию.
