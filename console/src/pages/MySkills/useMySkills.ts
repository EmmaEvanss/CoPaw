import { useState, useCallback } from "react";
import { mySkillsApi, MySkill } from "../../api/modules/mySkills";

export function useMySkills(sourceId: string, userId: string) {
  const [createdSkills, setCreatedSkills] = useState<MySkill[]>([]);
  const [receivedSkills, setReceivedSkills] = useState<MySkill[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [created, received] = await Promise.all([
        mySkillsApi.getCreatedSkills(sourceId, userId),
        mySkillsApi.getReceivedSkills(sourceId, userId),
      ]);
      setCreatedSkills(created);
      setReceivedSkills(received);
    } catch (err) {
      console.error("Failed to load my skills:", err);
    } finally {
      setLoading(false);
    }
  }, [sourceId, userId]);

  return {
    createdSkills,
    receivedSkills,
    loading,
    refresh,
  };
}
