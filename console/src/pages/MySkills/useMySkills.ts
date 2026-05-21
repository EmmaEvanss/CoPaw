import { useState, useCallback } from "react";
import { mySkillsApi, MySkill } from "../../api/modules/mySkills";

export function useMySkills() {
  const [createdSkills, setCreatedSkills] = useState<MySkill[]>([]);
  const [receivedSkills, setReceivedSkills] = useState<MySkill[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [created, received] = await Promise.all([
        mySkillsApi.getCreatedSkills(),
        mySkillsApi.getReceivedSkills(),
      ]);
      setCreatedSkills(created);
      setReceivedSkills(received);
    } catch (err) {
      console.error("Failed to load my skills:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSkill = useCallback(async (skillName: string): Promise<MySkill | null> => {
    try {
      const [created, received] = await Promise.all([
        mySkillsApi.getCreatedSkills(),
        mySkillsApi.getReceivedSkills(),
      ]);

      // 更新列表
      setCreatedSkills(created);
      setReceivedSkills(received);

      // 返回刷新后的技能
      const allSkills = [...created, ...received];
      return allSkills.find(s => s.skill_name === skillName) || null;
    } catch (err) {
      console.error("Failed to refresh skill:", err);
      return null;
    }
  }, []);

  return {
    createdSkills,
    receivedSkills,
    loading,
    refresh,
    refreshSkill,
  };
}
