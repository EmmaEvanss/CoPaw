import { createGlobalStyle } from "antd-style";

export default createGlobalStyle`
.task-progress-floating {
  margin: 0 0 8px 0;
  max-height: 220px;
  overflow-y: auto;
  background: ${(p) => p.theme.colorBgElevated};
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), 0 1px 4px rgba(0, 0, 0, 0.08);
  border: 1px solid ${(p) => p.theme.colorBorderSecondary};

  &-progress-bar {
    height: 3px;
    background: ${(p) => p.theme.colorFillSecondary};
    border-radius: 10px 10px 0 0;
    overflow: hidden;

    &-fill {
      height: 100%;
      background: linear-gradient(90deg, ${(p) => p.theme.colorPrimary}, ${(p) => p.theme.colorPrimary}99);
      border-radius: 0 1.5px 1.5px 0;
      transition: width 0.4s ease;
    }
  }

  &-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    cursor: pointer;
    user-select: none;
  }

  &-header-icon {
    font-size: 14px;
    color: ${(p) => p.theme.colorTextSecondary};
  }

  &-header-title {
    font-size: 13px;
    font-weight: 600;
    color: ${(p) => p.theme.colorText};
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &-header-badge {
    margin-left: auto;
    font-size: 11px;
    color: ${(p) => p.theme.colorPrimary};
    background: ${(p) => p.theme.colorPrimaryBg};
    padding: 1px 8px;
    border-radius: 10px;
    font-weight: 500;
    flex-shrink: 0;
  }

  &-header-arrow {
    font-size: 12px;
    color: ${(p) => p.theme.colorTextQuaternary};
    transition: transform 0.2s ease;
    flex-shrink: 0;

    &--collapsed {
      transform: rotate(-90deg);
    }
  }

  &-divider {
    margin: 0 14px;
    border-bottom: 1px solid ${(p) => p.theme.colorBorderSecondary};
  }

  &-list {
    padding: 4px 0;
  }

  &-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 14px;
    transition: background-color 0.2s ease;

    &--running {
      background: ${(p) => p.theme.colorPrimaryBg};
    }
  }

  &-item-icon {
    width: 16px;
    height: 16px;
    flex-shrink: 0;

    &--todo {
      width: 16px;
      height: 16px;
      border: 1.5px solid ${(p) => p.theme.colorBorderSecondary};
      border-radius: 50%;
    }

    &--running, &--done, &--spin {
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    &--running, &--spin {
      color: ${(p) => p.theme.colorPrimary};
    }

    &--done {
      color: ${(p) => p.theme.colorSuccess};
    }
  }

  &-item-label {
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    &--todo {
      color: ${(p) => p.theme.colorTextQuaternary};
    }

    &--running {
      color: ${(p) => p.theme.colorPrimary};
      font-weight: 500;
    }

    &--done {
      color: ${(p) => p.theme.colorTextQuaternary};
      text-decoration: line-through;
    }
  }

  &--completed {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: ${(p) => p.theme.colorSuccessBg};
    border: 1px solid ${(p) => p.theme.colorSuccessBorder};
    border-radius: 10px;
    color: ${(p) => p.theme.colorSuccess};
    font-size: 13px;
    font-weight: 500;
    animation: task-progress-fade-out 0.5s 1s forwards;
  }

  &--cancelled {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: ${(p) => p.theme.colorFillTertiary};
    border: 1px solid ${(p) => p.theme.colorBorderSecondary};
    border-radius: 10px;
    color: ${(p) => p.theme.colorTextTertiary};
    font-size: 13px;
    font-weight: 500;
    animation: task-progress-fade-out 0.3s 0.5s forwards;
  }

  @keyframes task-progress-fade-out {
    to { opacity: 0; }
  }
}
`;
