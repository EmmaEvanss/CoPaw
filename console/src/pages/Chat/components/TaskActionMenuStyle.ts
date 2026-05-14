import { createGlobalStyle } from "antd-style";

export default createGlobalStyle`
.task-action-menu-dropdown {
  .ant-dropdown-menu {
    min-width: 220px;
    padding: 8px;
    border: 1px solid rgba(17, 20, 45, 0.08);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.98);
    box-shadow:
      0 16px 40px rgba(17, 20, 45, 0.12),
      0 2px 8px rgba(17, 20, 45, 0.06);
  }

  .ant-dropdown-menu-item {
    min-height: 52px;
    padding: 8px 10px;
    border-radius: 8px;
    color: #11142D;
    transition:
      background-color 0.14s ease,
      color 0.14s ease;

    &:hover {
      background: rgba(55, 105, 252, 0.07);
    }
  }

  .ant-dropdown-menu-item-danger {
    color: #FE2842;

    &:hover {
      background: rgba(254, 40, 66, 0.07);
    }
  }

  .ant-dropdown-menu-item-divider {
    margin: 6px 4px;
    background: rgba(17, 20, 45, 0.08);
  }
}

.task-action-menu-label {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-action-menu-label-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  color: #6B6F80;
}

.task-action-menu-label-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.task-action-menu-label-title {
  font-size: 13px;
  line-height: 18px;
  font-weight: 600;
  color: #11142D;
}

.task-action-menu-label-description {
  font-size: 12px;
  line-height: 16px;
  font-weight: 400;
  color: #8B8FA1;
  white-space: nowrap;
}

.task-action-menu-label--danger {
  .task-action-menu-label-icon,
  .task-action-menu-label-title {
    color: #FE2842;
  }
}
`;
