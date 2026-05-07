## 1. Backend Service

- [ ] 1.1 Create `src/swe/app/workspace/file_broadcast.py` with `BROADCASTABLE_FILES` whitelist, `BroadcastFileTenantResult` and `BroadcastFilesResponse` Pydantic models
- [ ] 1.2 Implement `FileBroadcastService` class with `_validate_tenant_id()` static method for tenant ID sanitization
- [ ] 1.3 Implement `FileBroadcastService._copy_to_tenant()` blocking method using `TenantInitializer` + `shutil.copy2`
- [ ] 1.4 Implement `FileBroadcastService.broadcast()` async method with per-tenant error isolation via `asyncio.to_thread`

## 2. Backend API Endpoints

- [ ] 2.1 Add `GET /workspace/broadcast/tenants` endpoint in `src/swe/app/routers/workspace.py` using `list_logical_tenant_ids()`
- [ ] 2.2 Add `POST /workspace/broadcast/files` endpoint with `BroadcastFilesRequest` model
- [ ] 2.3 Add `overwrite=true` enforcement check in the endpoint
- [ ] 2.4 Add source file existence pre-validation in the endpoint
- [ ] 2.5 Add broadcastable files whitelist validation in the endpoint

## 3. Frontend API Layer

- [ ] 3.1 Add `BroadcastFileTenantResult` and `BroadcastFilesResponse` types in `console/src/api/types/workspace.ts`
- [ ] 3.2 Add `listBroadcastTenants()` method in `console/src/api/modules/workspace.ts`
- [ ] 3.3 Add `broadcastFiles()` method in `console/src/api/modules/workspace.ts`

## 4. Frontend Components

- [ ] 4.1 Add `selectable`, `broadcastSelected`, `onSelectToggle` props to `FileItem` component with "选择/已选择" button
- [ ] 4.2 Extend `FileListPanel` props to pass through `selectable`, `broadcastSelected`, `onSelectToggle`
- [ ] 4.3 Delete `FileBroadcastModal.tsx` component

## 5. Frontend Page Logic

- [ ] 5.1 Add broadcast state variables in `index.tsx`: `selectedFileNames`, `broadcastOpen`, `broadcastLoading`, `broadcastSubmitting`, `broadcastTenantIds`, `selectedTenantIds`
- [ ] 5.2 Implement `openBroadcastModal()` with async tenant loading and current tenant filtering
- [ ] 5.3 Implement `handleBroadcastConfirm()` with API call and success/failure result dialogs
- [ ] 5.4 Add inline `<Modal>` in `index.tsx` with hint, overwrite warning, `TenantTargetPicker`
- [ ] 5.5 Add "分发" button with `SendOutlined` and selection count badge in PageHeader

## 6. Frontend Styles

- [ ] 6.1 Add `.broadcastSelected` blue border style in `index.module.less`
- [ ] 6.2 Add `.selectButton` / `.selectButtonActive` styles
- [ ] 6.3 Add `.distributionWarning` orange warning box style
- [ ] 6.4 Add `.selectionSummary` count badge style
- [ ] 6.5 Add dark mode variants for all new styles

## 7. i18n

- [ ] 7.1 Add broadcast-related i18n keys to `zh.json`
- [ ] 7.2 Add broadcast-related i18n keys to `en.json`
- [ ] 7.3 Add broadcast-related i18n keys to `ru.json`
- [ ] 7.4 Add broadcast-related i18n keys to `ja.json`
