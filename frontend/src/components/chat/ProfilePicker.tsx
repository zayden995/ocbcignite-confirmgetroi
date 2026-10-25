import { useTree } from "../../context/TreeContext";

/** Who is asking. TREE only trusts policies written for this role and region (see the note below the selects). */
export function ProfilePicker({ withNote = false }: { withNote?: boolean }) {
  const { meta, role, region, setRole, setRegion } = useTree();
  return (
    <div className="profile-picker">
      <div className="profile-line">
        <span>Asking as</span>
        <label className="sr-only" htmlFor="role-select">Role</label>
        <select id="role-select" value={role} onChange={(e) => setRole(e.target.value)}>
          {meta?.roles.map((r) => (
            <option key={r.code} value={r.code}>{r.label}</option>
          ))}
        </select>
        <span>in</span>
        <label className="sr-only" htmlFor="region-select">Region</label>
        <select id="region-select" value={region} onChange={(e) => setRegion(e.target.value)}>
          {meta?.regions.map((r) => (
            <option key={r.code} value={r.code}>{r.label}</option>
          ))}
        </select>
      </div>
      {withNote && (
        <p className="profile-note">
          Policies are written for specific roles and regions. TREE checks that an answer relies on ones that apply to you, so the
          same answer can be right for one employee and wrong for another. Try changing these after you ask.
        </p>
      )}
    </div>
  );
}
