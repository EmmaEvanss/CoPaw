import { useState, useCallback } from "react";
import { marketApi, Category, MarketSkill, MarketSkillDetail } from "../../api/modules/market";

export function useMarket(sourceId: string) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [skills, setSkills] = useState<MarketSkill[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<MarketSkillDetail | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);

  const refreshCategories = useCallback(async () => {
    try {
      const data = await marketApi.listCategories(sourceId);
      setCategories(data);
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  }, [sourceId]);

  const refreshSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await marketApi.listMarketSkills(sourceId, selectedCategory ?? undefined);
      setSkills(data);
    } catch (err) {
      console.error("Failed to load skills:", err);
    } finally {
      setLoading(false);
    }
  }, [sourceId, selectedCategory]);

  const openSkillDetail = useCallback(
    async (itemId: string) => {
      try {
        const detail = await marketApi.getSkillDetail(sourceId, itemId);
        if (detail) {
          setSelectedSkill(detail);
          setDetailDrawerOpen(true);
        }
      } catch (err) {
        console.error("Failed to load skill detail:", err);
      }
    },
    [sourceId]
  );

  return {
    categories,
    skills,
    loading,
    selectedCategory,
    setSelectedCategory,
    selectedSkill,
    detailDrawerOpen,
    setDetailDrawerOpen,
    publishModalOpen,
    setPublishModalOpen,
    refreshCategories,
    refreshSkills,
    openSkillDetail,
  };
}
